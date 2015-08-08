#!/usr/bin/env python
# coding : utf-8
import sqlobject
import os
import hashlib
import binascii
import sys

from user import *

DB_PATH = '/mnt/hgfs/sas/sources/sms-gateway/src/sms.db'

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'please enter user name'
        exit(1)
    sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH)
    User.createTable(ifNotExists=True)
    user_object = User.select(User.q.login == sys.argv[1])
    try:
        db_user = user_object.getOne()
        print('User already exists')
        exit(1)
    except:
        passwd = raw_input()
        test = User(login=sys.argv[1])
        test.password = passwd
