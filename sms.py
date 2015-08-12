# coding : utf-8
class SMS(object):
    def __init__(self, number, message, queue):
        self.number = number
        self.message = message
        self.queue = queue
