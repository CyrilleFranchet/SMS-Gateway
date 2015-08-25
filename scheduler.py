# coding : utf-8
import threading
import binascii
import Queue
from collections import OrderedDict

from sms import *

from global_var import *

class Scheduler(threading.Thread):
    def __init__(self, fifo):
        self.debug = debug
        self.stop = threading.Event()
        self.dict_jobs_to_procede = OrderedDict()
        self.id = 0
        self.fifo = fifo
        self.lock = threading.Lock()
        threading.Thread.__init__(self)

    def SchedulerAddJob(self, username, number, message):
        # Add the SMS in workqueue
        new_sms = SMS(username, number, message, Queue.Queue(1))
        self.lock.acquire()
        self.id += 1
        temp_id = self.id
        self.lock.release()
        self.dict_jobs_top_rocede[temp_id] = new_sms
        return temp_id

    def SchedulerGetJob(self, username, id):
        pass

    def run(self):
        while not self.stop.isSet():
            while self.dict_jobs:
                _, sms = self.dict_jobs_to_procede.popitem(last=False)
                if self.debug: print 'Sending SMS into FIFO', sms
                self.fifo.put(sms, True, 5)
                self.fifo.join()
                try:
                    modem_response = sms.queue.get(True, 15)
                except Queue.Empty:
                    pass
                print 'Scheduler received modem response :', modem_response
                sms.queue.task_done()
