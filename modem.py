# coding : utf-8
import RPi.GPIO as GPIO
import serial
import time
import threading
import Queue

from global_var import *

class Modem(threading.Thread):
    def GSMWakeUp(self):
        GPIO.output(7,True)
        time.sleep(0.5)
        GPIO.output(7,False)
    
    def __init__(self, pin):
        self.pin = pin
        self.debug = debug
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(7, GPIO.OUT)
        self.sr = serial.Serial('/dev/ttyAMA0', 9600, timeout=5)
        self.stop = threading.Event()
        self.fifo = Queue.Queue(1)
        threading.Thread.__init__(self)
    
    def getFifo(self):
        return self.fifo

    def GSMSendATCommand(self, command):
        self.sr.write(str.encode(command+"\r\n"))
        ret = []
        while True:
            msg = self.sr.readline().strip().decode('ascii')
            if msg != "":
                ret.append(msg)
                if msg == 'OK':
                    break
                elif msg == 'ERROR':
                    break
                elif msg == '>':
                    break
        if self.debug: print(command,"output is", ret)
        return ret
    
    def GSMShutdown(self):
        ret = self.GSMSendATCommand("AT^SMSO")
        for elem in ret:
            if elem == 'OK':
                return 0
        return 1
    
    def run(self):
        if self.debug: print 'Waking up the GSM board'
        self.GSMWakeUp()
        # We need to wait for the modem to start
        time.sleep(3)
        while not self.stop.isSet():
            # Retrieve the new SMS in the FIFO
            try:
                new_sms = self.fifo.get(timeout=1)
                print 'modem is reading', new_sms
                # Tell the producer that the job is over
                self.fifo.task_done()
                new_sms.queue.put(0)
            except:
                pass
        if self.debug: print 'Shutting down the GSM board'
        self.GSMShutdown()
        GPIO.cleanup()
