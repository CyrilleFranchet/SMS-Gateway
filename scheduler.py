# coding : utf-8
import threading
import binascii
import Queue
from collections import OrderedDict

class Scheduler(threading.Thread):
    def __init__(self, pin):
        self.debug = debug
        self.dict_jobs = OrderedDict()
        self.stop = threading.Event()
        threading.Thread.__init__(self)
    
    def SchedulerAddJob(self, sms):
        # Generate a new job id
        id = binascii.hexlify(os.urandom(5))
        while id in self.dict_jobs:
            id = binascii.hexlify(os.urandom(5))
        self.dict_jobs[id] = sms

    def SchedulerGetJobs(self):
        return self.dict_jobs

    def run(self):
        while not self.stop.isSet():
            while self.dict_jobs:
                temp_fifo = Queue.Queue(1)
                _, sms = self.dict_jobs.popitem(last=False)
                fifo.put(sms, True, 5)
                fifo.join()
                modem_response = temp_fifo.get(True, 5)
                temp_fifo.task_done()
             
