import sqlite3
import threading
import time
import datetime

SQLITE_FILE = 'wikiteam_bot.sqlite3'
from rich import print


DB_LOCK = threading.Lock()

def db_lock(func):
    def wrapper(*args, **kwargs):
        with DB_LOCK:
            return func(*args, **kwargs)
    return wrapper

class Singleton(object):
    def __init__(self, cls):
        self._cls = cls
        self._instance = {}
    def __call__(self):
        if self._cls not in self._instance:
            self._instance[self._cls] = self._cls()
        return self._instance[self._cls]

@Singleton
class BotDB(threading.local):

    conn = None # type: sqlite3.Connection

    def __init__(self):
        print('Using DB: %s' % SQLITE_FILE)
        self.conn = sqlite3.connect(SQLITE_FILE)
        # self.createDB()

    def createDB(self):
        # page_id as primary key （int）
        # last_success_check as DATE
        # ia_identifier as TEXT
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS wikiteam_bot ( page_id INTEGER PRIMARY KEY, last_success_check DATE, ia_identifier TEXT )''')

    @db_lock
    def createPage(self, page_id: int):
        c = self.conn.cursor()
        c.execute('''INSERT INTO wikiteam_bot (page_id, last_success_check) VALUES (?, CURRENT_DATE)''', (page_id,))
        self.conn.commit()

    @db_lock
    def updatePageCheckDate(self, page_id: int):
        c = self.conn.cursor()
        c.execute('''UPDATE wikiteam_bot SET last_success_check = CURRENT_DATE WHERE page_id = ?''', (page_id,))
        self.conn.commit()

    @db_lock
    def isExiest(self, page_id: int)-> bool:
        c = self.conn.cursor()
        c.execute('''SELECT page_id FROM wikiteam_bot WHERE page_id = ?''', (page_id,))
        result = c.fetchone()
        if result:
            return True
        else:
            return False

    @db_lock
    def __get_last_success_check_raw(self, page_id: int):
        c = self.conn.cursor()
        # strftime()
        c.execute('''SELECT last_success_check FROM wikiteam_bot WHERE page_id = ?''', (page_id,))
        result = c.fetchone()
        if result:
            return result[0]
        else:
            raise Exception('Page not found')

    def get_last_success_check_timestamp(self, page_id: int)-> int:
        result = self.__get_last_success_check_raw(page_id)
        return int(time.mktime(datetime.datetime.strptime(result, "%Y-%m-%d").timetuple()))

    @db_lock
    def get_identifier(self, page_id)-> str:
        c = self.conn.cursor()
        c.execute('''SELECT ia_identifier FROM wikiteam_bot WHERE page_id = ?''', (page_id,))
        result = c.fetchone()
        if result:
            return result[0]
        else:
            raise Exception('Page not found')
    
    @db_lock
    def set_identifier(self, page_id: int, identifier: str):
        c = self.conn.cursor()
        c.execute('''UPDATE wikiteam_bot SET ia_identifier = ? WHERE page_id = ?''', (identifier, page_id))
        self.conn.commit()

    @db_lock
    def close(self):
        print('[red]Closing DB connection...[/red]')
        self.conn.close()

    def __del__(self):
        self.close()
