#!/usr/bin/env python
# coding : utf-8

import RPi.GPIO as GPIO
import serial
import time
import threading
import Queue
import logging
from curses import ascii

class TimeoutOnSerial(Exception):
    pass

class Modem(threading.Thread):
    name = 'APIModemThread'
    
    def gsm_wakeup(self):
        GPIO.output(7,True)
        time.sleep(0.5)
        GPIO.output(7,False)
    
    def __init__(self, pin):
        self.pin = pin
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(7, GPIO.OUT)
        self.sr = serial.Serial('/dev/ttyAMA0', 9600, timeout=5)
        self.stop = threading.Event()
        self.fifo = Queue.Queue(1)
        self.logger = logging.getLogger('api')
        threading.Thread.__init__(self)
    
    def get_fifo(self):
        return self.fifo

    def gsm_send_AT_command(self, command):
        data = command + '\r'
        self.sr.write(data.encode('ascii'))
        ret = []
        orig_time = time.time()
        while self.sr.inWaiting() == 0:
            if time.time() - orig_time > 10:
                raise TimeoutOnSerial('Could not read on serial port')
        while True:
            msg = self.sr.readline().strip()
            ret.append(msg)
            if msg != "":
                if msg == 'OK':
                    break
                elif msg == 'ERROR':
                    break
                elif msg == '>':
                    break
        return ret
    
    def gsm_shutdown(self):
        ret = self.gsm_send_AT_command('AT^SMSO')
        for elem in ret:
            if elem == 'OK':
                return 0
        return 1
    
    def gsm_is_ready(self):
        self.sr.write(str.encode('AT\r\n'))
        ret = []
        time.sleep(1)
        while self.sr.inWaiting() > 0:
            msg = self.sr.readline().strip().decode('ascii')
            if msg != "":
                ret.append(msg)
        if len(ret) > 0 and ret[0] == 'OK':
            return True
        else:
            return False

    def gsm_sms_send(self, number, message):
        ret = self.gsm_send_AT_command('AT+CMGS="'+number+'",145')
        if '>' in ret:
            ret = self.gsm_send_AT_command(message+ascii.ctrl('z'))
            if 'OK' in ret:
                return True
        return False

    def gsm_sms_textmode(self):
        ret = self.gsm_send_AT_command('AT+CMGF=1')
        if 'OK' in ret:
            return True
        return False

    def gsm_sim_unlock(self, pin):
        ret = self.gsm_send_AT_command('AT+CPIN='+pin)
        if len(ret) > 0 and ret[0].startswith('OK'):
            return False
        return True

    def gsm_sim_is_locked(self):
        ret = self.gsm_send_AT_command('AT+CPIN?')
        if '+CPIN: READY' in ret:
            return False
        return True

    def run(self):
        self.gsm_wakeup()
        while not self.gsm_is_ready():
            time.sleep(1)
        if self.gsm_sim_is_locked():
            self.gsm_sim_unlock(self.pin)
        # We need to wait for the modem to start
        time.sleep(3)
        while not self.stop.isSet():
            # Retrieve the new SMS in the FIFO
            try:
                new_sms = self.fifo.get(timeout=1)
            except:
                pass
            else:
                try:
                    if self.gsm_sms_textmode():
                        sms_status = self.gsm_sms_send(new_sms.number, new_sms.message)
                except TimeoutOnSerial:
                    response = 'failed'
                else:
                    response = 'sent'
                finally:
                    # Tell the producer that the job is over
                    self.fifo.task_done()
                    new_sms.queue.put(response)
        self.gsm_shutdown()
        self.sr.close()
        GPIO.cleanup()
