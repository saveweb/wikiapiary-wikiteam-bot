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
import requests

import pywikibot
import pywikibot.pagegenerators, pywikibot.config
from internetarchive.session import ArchiveSession
from internetarchive.search import Search
# import urllib.parse

def main():
    session = requests.Session() # requests session
    ia_session = ArchiveSession() # internetarchive session
    site = pywikibot.Site('wikiapiary', 'wikiapiary')
    print('Logging in as %s' % (site.username()))
    site.login()
    print('Logged in as %s' % (site.user()))
    catname = 'Category:Website'

    cat = pywikibot.Category(site, catname)
    gen = pywikibot.pagegenerators.CategorizedPageGenerator(cat, start='!')
    pre = pywikibot.pagegenerators.PreloadingGenerator(gen)
    
    # print bot information
    pywikibot.output('WikiApiary bot starting...')

    for page in pre:
        if page.isRedirectPage():
            continue
        
        wtitle = page.title()
        wtext = page.text
        ia_in_wikitext = False
        
        #if not wtitle.startswith('5'):
        #    continue
        
        if '|Internet Archive' in wtext:
            print('It has IA parameter')
            ia_in_wikitext = True
        #     pass
        # else:
            print('\n','#'*50,'\n',wtitle,'\n','#'*50)
            print('https://wikiapiary.com/wiki/%s' % (re.sub(' ', '_', wtitle)))
            print('Missing IA parameter')

            # continue
            
            if re.search(r'(?i)API URL=http', wtext):
                apiurl = re.findall(r'(?i)API URL=(http[^\n]+?)\n', wtext)[0]
                print('API:', apiurl)
            else:
                print('No API found in WikiApiary, skiping')
                continue

            # continue
            
            indexurl = 'index.php'.join(apiurl.rsplit('api.php', 1))
            print('Index:', indexurl)
            # url_ia_search = 'https://archive.org/services/search/beta/page_production/'

            ia_search_params = {
                'sort': '-date',
            }
            query = f'(originalurl:"{apiurl}" OR originalurl:"{indexurl}")'
            search = Search(ia_session, query=query,
                            fields=['identifier', 'addeddate', 'subject', 'uploader'],
                            sorts=['addeddate desc'] # newest first
                            )
            item = None
            for result in search:
                print(result)
                # {'identifier': 'wiki-wikiothingxyz-20230315',
                # 'addeddate': '2023-03-15T01:42:12Z',
                # 'subject': ['wiki', 'wikiteam', 'MediaWiki', .....]}
                item = result
                break
            if item is None:
                print('No dumps found at Internet Archive')
                continue

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
            

            if ia_in_wikitext:
                # remove old IA parameters
                print('Removing old IA parameters')
                wtext = page.text
                wtext = re.sub(r'(?im)\|Internet Archive identifier=[^\n]+?\n', '', wtext)
                wtext = re.sub(r'(?im)\|Internet Archive URL=[^\n]+?\n', '', wtext)
                wtext = re.sub(r'(?im)\|Internet Archive added date=[^\n]+?\n', '', wtext)
                wtext = re.sub(r'(?im)\|Internet Archive file size=[^\n]+?\n', '', wtext)
                # wtext = re.sub(r'(?im)\n\}\}', '\n}}', wtext)

            time_sufs = ['00:00:00 ','12:00:00 AM']
            need_edit = True
            for time_suf in time_sufs:
                iaparams = """|Internet Archive identifier=%s
|Internet Archive URL=%s
|Internet Archive added date=%s %s
|Internet Archive file size=%s""" % (item_identifier, item_url, item_date, time_suf, dump_size)
                newtext = wtext
                newtext = re.sub(r'(?im)\n\}\}', '\n%s\n}}' % (iaparams), newtext)
                
                if page.text == newtext:
                    need_edit = False
                    break

            if not need_edit:
                print('Same IA parameters, skiping...')
                continue

            pywikibot.showDiff(page.text, newtext)
            page.text = newtext
            edit_type = 'Updating' if ia_in_wikitext else 'Adding'
            # print('BOT - %s dump details: %s, %s, %s bytes' % (edit_type ,item_identifier, item_date, dump_size))
            page.save('BOT - %s dump details: %s, %s, %s bytes' % (edit_type ,item_identifier, item_date, dump_size), botflag=True)
            

if __name__ == "__main__":
    main()

