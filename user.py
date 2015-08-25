# coding : utf-8
import sqlobject
import binascii
import os
import hashlib
DB_PATH = os.path.dirname(os.path.abspath(__file__)) + '/sms.db'

class User(sqlobject.SQLObject):
    # id is implicit
    login = sqlobject.StringCol(notNone=True, unique=True)
    password = sqlobject.StringCol(default=None)
    salt = sqlobject.StringCol(length=10, default=binascii.hexlify(os.urandom(5)))
    token = sqlobject.StringCol(length=32, default=None)
    ###expirationDate = sqlobject.DateTimeCol(default=None)

    def _set_password(self, value):
        if value:
            self._SO_set_password(hashlib.pbkdf2_hmac('sha256', value, self.salt, 100000))
