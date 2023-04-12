# -*- coding: utf-8 -*-

# Copyright (C) 2016 WikiTeam
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import time
import os
import urllib.parse
import threading


import pywikibot
import pywikibot.pagegenerators, pywikibot.config
from internetarchive.session import ArchiveSession
from internetarchive.search import Search
import requests
# from rich import print
from rich import print as rich_print

from utils.database import BotDB
from utils.delay_write_page import delay_write_page, set_last_page_write_time
from utils.session import createSession
from utils.util import need_stop, resume_title, write_resume_title
from utils.wikitext import insert_iaparams_to_wikitext
from wikiteam_bot_config import IA_MAX_RETRY, THREAD_NUM, UPDATE_INTERVAL

print_lock = threading.Lock()
def print_with_lock_and_thread(*args, **kwargs):
    print_lock.acquire()
    rich_print('thread %s' % threading.current_thread().name, end=': ')
    rich_print(*args, **kwargs)
    print_lock.release()

print = print_with_lock_and_thread


def main():
    db = BotDB()
    db.createDB()
    session = createSession() # requests session
    ia_session = ArchiveSession() # internetarchive session
    session = ia_session
    site = pywikibot.Site('wikiapiary', 'wikiapiary')
    print('Logging in as %s' % (site.username()))
    site.login()
    print('Logged in as %s' % (site.user()))
    catname = 'Category:Website'
    start = resume_title() if resume_title() else '!'
    print('start from', start)

    cat = pywikibot.Category(site, catname)
    gen = pywikibot.pagegenerators.CategorizedPageGenerator(cat, start=start)
    pre = pywikibot.pagegenerators.PreloadingGenerator(gen)
    
    # print bot information
    pywikibot.output('WikiApiary bot starting...')

    threads = []

    lowest_page_title = None
    offset = THREAD_NUM
    for page in pre:
        if need_stop():
            print('stop file found, exiting...')
            break
        if page.isRedirectPage():
            continue

        threads.append(threading.Thread(target=check_page, args=(page, db, session, ia_session)))
        threads[-1].start()
        while len(threads) >= THREAD_NUM:
            for t in threads:
                if not t.is_alive():
                    threads.remove(t)
            time.sleep(1)

        offset -= 1
        if offset == 0:
            lowest_page_title = page.title()
            write_resume_title(lowest_page_title)
            offset = THREAD_NUM


    # close pywikibot http session
    pywikibot.stopme()

    if not need_stop():
        # complete. not stoped by user, remove resume.txt
        print('-- Done --')
        os.remove('resume.txt')

page_write_lock = threading.Lock()

def check_page(page, db: BotDB, session: requests.Session, ia_session: ArchiveSession):
    wtitle = page.title()
    w_page_id = int(page.pageid)
    # print thread name
    # print(threading.current_thread().name)
    print('####################', w_page_id, '####################')
    print('"https://wikiapiary.com/wiki/%s"' % urllib.parse.quote(wtitle))

    if (db.isExiest(w_page_id)
        and db.get_last_success_check_timestamp(w_page_id) > time.time() - UPDATE_INTERVAL): # 24 hours
        print(f'pid: {w_page_id}, title: {wtitle} is already checked in last {UPDATE_INTERVAL/86400} days')
        return # skip

    old_text = page.text
    ia_in_wikitext = False
    if '|Internet Archive' in old_text:
        print('It has IA parameter')
        ia_in_wikitext = True
    else:
        print('Missing IA parameter')


    if re.search(r'(?i)API URL=http', old_text):
        apiurl: str = re.findall(r'(?i)API URL=(http[^\n]+?)\n', old_text)[0]
        print('API:', apiurl)
    else:
        print('No API found in WikiApiary, skiping')
        return # skip

    # continue
    
    indexurl = 'index.php'.join(apiurl.rsplit('api.php', 1))
    print('Index:', indexurl)

    query = f'(originalurl:"{apiurl}" OR originalurl:"{indexurl}")'
    search = Search(ia_session, query=query,
                    fields=['identifier', 'addeddate', 'subject', 'originalurl', 'uploader'],
                    sorts=['addeddate desc'], # newest first
                    max_retries=IA_MAX_RETRY, # default 5
                    )
    item = None
    for result in search: # only get the first result
        print(result)
        # {'identifier': 'wiki-wikiothingxyz-20230315',
        # 'addeddate': '2023-03-15T01:42:12Z',
        # 'subject': ['wiki', 'wikiteam', 'MediaWiki', .....]}
        if apiurl.lower == result['originalurl'].lower or indexurl.lower == result['originalurl'].lower:
            print('Original URL not match, skiping...')
            break

        item = result
        break
    if item is None:
        print('No suitable dump found at Internet Archive')
        db.createPage(w_page_id) if not db.isExiest(w_page_id) else db.updatePageCheckDate(w_page_id)
        return # skip

    item_identifier = item['identifier']
    item_url = 'https://archive.org/details/%s' % item_identifier
    print('Item found:',item_url)
    
    metaurl = 'https://archive.org/download/%s/%s_files.xml' % (item_identifier, item_identifier)
    r = session.get(metaurl)
    r.raise_for_status()
    raw2 = r.text
    raw2 = raw2.split('</file>')
    item_files = []
    for raw2_ in raw2:
        try:
            x = re.findall(r'(?im)<file name="[^ ]+-(\d{8})-[^ ]+" source="original">', raw2_)[0]
            y = re.findall(r'(?im)<size>(\d+)</size>', raw2_)[0]
            item_files.append([int(x), int(y)])
        except:
            pass
        
    item_files.sort(reverse=True)
    print(item_files)
    item_date = str(item_files[0][0])[0:4] + '/' + str(item_files[0][0])[4:6] + '/' + str(item_files[0][0])[6:8]
    dump_size = item_files[0][1]
    
    old_text: str = page.text
    if ia_in_wikitext:
        # remove old IA parameters
        print('Removing old IA parameters')
        old_text = re.sub(r'(?im)\|Internet Archive identifier[^\n]*?\n', '', old_text)
        old_text = re.sub(r'(?im)\|Internet Archive URL=[^\n]*?\n', '', old_text)
        old_text = re.sub(r'(?im)\|Internet Archive added date=[^\n]*?\n', '', old_text)
        old_text = re.sub(r'(?im)\|Internet Archive file size=[^\n]*?\n', '', old_text)
        # wtext = re.sub(r'(?im)\n\}\}', '\n}}', wtext)

    time_sufs = ['00:00:00 ','12:00:00 AM']
    need_edit = True
    newtext = None
    for time_suf in time_sufs:
        iaparams = """|Internet Archive identifier=%s
|Internet Archive URL=%s
|Internet Archive added date=%s %s
|Internet Archive file size=%s""" % (item_identifier, item_url, item_date, time_suf, dump_size)
        # newtext = re.sub(r'(?im)\n\}\}', '\n%s\n}}' % (iaparams), newtext)
        newtext = insert_iaparams_to_wikitext(iaparams=iaparams, wikitext=old_text)
        if newtext is None:
            need_edit = False
            break

        if newtext == old_text:
            need_edit = False
            break

        if iaparams in old_text:
            need_edit = False
            break

    if newtext is None:
        print('Skiping...')
        return

    if not need_edit:
        print('Same IA parameters, skiping...')
        db.createPage(w_page_id) if not db.isExiest(w_page_id) else db.updatePageCheckDate(w_page_id)
        db.set_identifier(w_page_id, item_identifier)
        return # skip

    pywikibot.showDiff(page.text, newtext)
    if (newtext.count('|Internet Archive identifier=') > 1 or
        newtext.count('|Internet Archive URL=') > 1        or
        newtext.count('|Internet Archive added date=') > 1 or
        newtext.count('|Internet Archive file size=') > 1
        ):
        print('Error: |Internet Archive parameters duplicated, you should fix it manually')
        print('Skiping...')
        return # skip

    page.text = newtext
    edit_type = 'Updating' if ia_in_wikitext else 'Adding'
    # print('BOT - %s dump details: %s, %s, %s bytes' % (edit_type ,item_identifier, item_date, dump_size))
    page_write_lock.acquire()
    delay_write_page()
    set_last_page_write_time()
    page.save('BOT - %s dump details: %s, %s, %s bytes' % (edit_type ,item_identifier, item_date, dump_size), botflag=True)
    page_write_lock.release()

    db.createPage(w_page_id) if not db.isExiest(w_page_id) else db.updatePageCheckDate(w_page_id)
    db.set_identifier(w_page_id, item_identifier)


if __name__ == "__main__":
    main()

