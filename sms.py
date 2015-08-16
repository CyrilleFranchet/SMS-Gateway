# coding : utf-8
import sqlobject

class SMS(object):
    def __init__(self, username, number, message, queue):
        self.username = username
        self.number = number
        self.message = message
        self.queue = queue
