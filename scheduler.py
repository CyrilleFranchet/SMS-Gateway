#!/usr/bin/env python
# coding : utf-8

import threading
import binascii
import Queue
import logging
from collections import OrderedDict

from sms import *

class Scheduler(threading.Thread):
    name = 'APISchedulerThread'
    
    def __init__(self, fifo):
        self.stop = threading.Event()
        self.dict_jobs_to_procede = OrderedDict()
        self.dict_jobs = {}
        self.id = 0
        self.fifo = fifo
        self.lock = threading.Lock()
        self.logger = logging.getLogger('api')
        threading.Thread.__init__(self)

    def SchedulerAddJob(self, username, number, message):
        # Add the SMS in workqueue
        new_sms = SMS(username, number, message, Queue.Queue(1))
        self.lock.acquire()
        self.id += 1
        temp_id = self.id
        self.lock.release()
        self.dict_jobs_to_procede[temp_id] = new_sms
        self.logger.info('Scheduling job id %i to %s from user %s' % (temp_id, number,username))
        return temp_id

    def SchedulerGetJob(self, username, id):
        if id in self.dict_jobs:
            if self.dict_jobs[id][0] == username:
                return self.dict_jobs[id][1]
            else:
                return 'forbidden'
        if id in self.dict_jobs_to_procede:
            if self.dict_jobs_to_procede[id].username == username:
                return 'queued'
            else:
                return 'forbidden'
        return 'unknown'

    def run(self):
        while not self.stop.isSet():
            if self.dict_jobs_to_procede:
                id, sms = self.dict_jobs_to_procede.popitem(last=False)
                self.logger.debug('Running job id %i' % id)
                self.dict_jobs[id] = [sms.username, 'sending']
                self.fifo.put(sms, True, 5)
                self.fifo.join()
                try:
                    modem_response = sms.queue.get(True, 15)
                    self.logger.info('Job id %i is marked as %s' % (id, modem_response))
                except:
                    # Got no response from modem
                    self.logger.info('Job id %i : no reply from modem' % id)
                    sms.queue.task_done()
                    self.dict_jobs[id] = [sms.username, 'unknown']
                else:
                    sms.queue.task_done()
                    self.dict_jobs[id] = [sms.username, modem_response]
