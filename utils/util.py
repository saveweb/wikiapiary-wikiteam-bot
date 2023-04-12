import os
import threading


def need_stop():
    if os.path.exists('stop'):
        return True
    return False


def resume_title():
    if not os.path.exists('resume.txt'):
        return None

    with open('resume.txt', 'r', encoding='utf-8') as f:
        title = f.read().splitlines()
        if title:
            return title[0]
    return None


resume_txt_write_lock = threading.Lock()
def write_resume_title(title):
    resume_txt_write_lock.acquire()
    with open('resume.txt', 'w', encoding='utf-8') as f:
        f.write(title)
    resume_txt_write_lock.release()