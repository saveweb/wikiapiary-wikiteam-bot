import time

from wikiteam_bot_config import GLOBAL_PAGE_WRITE_TOLERANCE


last_page_write_time = 0

def delay_write_page():
    global last_page_write_time
    # print("last_page_write_time: %s" % last_page_write_time)
    delay_time = 0
    if time.time() - last_page_write_time < GLOBAL_PAGE_WRITE_TOLERANCE:
        delay_time = GLOBAL_PAGE_WRITE_TOLERANCE - (time.time() - last_page_write_time)
        if delay_time <= 0:
            delay_time = 1
        print("page_write: delaying %s seconds" % int(delay_time))
    time.sleep(delay_time)

def set_last_page_write_time():
    global last_page_write_time
    last_page_write_time = time.time()