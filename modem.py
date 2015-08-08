# coding : utf-8
import RPi.GPIO as GPIO

class Modem(object):
    def __init__(self, pin):
        self.pin = pin
    def run(self):
        print 'in the thread'

