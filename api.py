#!/usr/bin/env python
# coding : utf-8

import BaseHTTPServer
from SocketServer import ThreadingMixIn
import urlparse
import phonenumbers
import json
import hashlib
import datetime
import threading
import logging

from sms import *
from user import *
from modem import *
from scheduler import *

# Define the API endpoints here
def auth(dict_query):
    param_username = dict_query['username'][0]
    param_password = dict_query['password'][0]
    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH+'?debug=1&logger='+__name__+'&loglevel=debug')
    else:
        sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH)

    # We need to create the tables
    User.createTable(ifNotExists=True)
    
    # We need to get the user object
    user_object = User.select(User.q.login == param_username)
    try:
        db_user = user_object.getOne()
        pbdkf2_password = hashlib.pbkdf2_hmac('sha256', param_password, db_user.salt, 100000)
        # Check if the password is correct
        if db_user.password == pbdkf2_password:
            # Check if a valid token is present in DB
            if db_user.token:
                pass
            else:
                db_user.token = binascii.hexlify(os.urandom(16))
            response = json.dumps({'response' : {'status' : 'success', 'token' : db_user.token}}, indent=4)
        else:
            response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'login or password incorrect'}}, indent=4)
        
    except sqlobject.SQLObjectIntegrityError as error:
        # We should not have more than one object returned
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'SQLi detected'}}, indent=4)
    except sqlobject.SQLObjectNotFound as error:
        # User doesn't not exist, fake the auth
        salt = "1234567890"
        pbdkf2_password = hashlib.pbkdf2_hmac('sha256', param_password, salt, 100000)
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'login or password incorrect'}}, indent=4)
    return response

def send(dict_query):
    param_number = dict_query['number'][0]
    param_token = dict_query['token'][0]
    param_message = dict_query['message'][0]
    
    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH+'?debug=1&logger='+__name__+'&loglevel=debug')
    else:
        sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH)
    
    try:
        obj_number = phonenumbers.parse(param_number, 'FR')
    except phonenumbers.NumberParseException as npe:
        if npe.error_type == 0:
            response = json.dumps({'response' : {'status' : 'failed', 'reason' : '\'%s\' is an unparseable phone number' % param_number }}, indent=4)
        elif npe.error_type == 1:
            response = json.dumps({'response' : {'status' : 'failed', 'reason' : '\'%s\' is not a phone number' % param_number }}, indent=4)
        return response
    if not phonenumbers.is_possible_number(obj_number):
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : '\'%s\' is an incorrect phone number' % param_number }}, indent=4)
        return response
    formated_number = phonenumbers.format_number(obj_number, phonenumbers.PhoneNumberFormat.E164)
    # Retrieve the token in database
    user_object = User.select(User.q.token == param_token)
    try:
        db_user = user_object.getOne()
    except sqlobject.SQLObjectIntegrityError as error:
        # We should not have more than one object returned
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'SQLi detected'}}, indent=4)
    except sqlobject.SQLObjectNotFound as error:
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'invalid token'}}, indent=4)
    else:
        # Add the job in the scheduler
        jobid = scheduler.SchedulerAddJob(db_user.login, formated_number, param_message)
        response = json.dumps({'response' : {'status' : 'queued', 'jobid' : jobid}}, indent=4)
    
    return response

def job(dict_query):
    param_token = dict_query['token'][0]
    try:
        param_id = int(dict_query['id'][0])
    except ValueError:
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'invalid id'}}, indent=4)
        return response

    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH+'?debug=1&logger='+__name__+'&loglevel=debug')
    else:
        sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH)
    # Retrieve the token in database
    user_object = User.select(User.q.token == param_token)
    try:
        db_user = user_object.getOne()
    except sqlobject.SQLObjectIntegrityError as error:
        # We should not have more than one object returned
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'SQLi detected'}}, indent=4)
    except sqlobject.SQLObjectNotFound as error:
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'invalid token'}}, indent=4)
    else:
        # Retrieve the job status from the scheduler
        jobstatus = scheduler.SchedulerGetJob(db_user.login, param_id)
        response = json.dumps({'response' : {'status' : 'success', 'job_status' : jobstatus, 'jobid' : param_id}}, indent=4)
    
    return response

# WebServer classes
class MyThreadingMixIn(ThreadingMixIn):
    def process_request(self, request, client_address):
        """Start a new thread to process the request."""
        t = threading.Thread(name = 'APIHTTPClientThread', target = self.process_request_thread,
                             args = (request, client_address))
        t.daemon = self.daemon_threads
        t.start()

class ThreadedHTTPServer(MyThreadingMixIn, BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, dict_endpoints):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.RequestHandlerClass.dict_endpoints = dict_endpoints

class WebServer(BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, dict_endpoints):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.RequestHandlerClass.dict_endpoints = dict_endpoints
                         
class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, request, client_address, server)
        self.dict_endpoints = None
    
    def log_message(self, format, *args):
        elems = (self.client_address[0], self.client_address[1]) + args
        formats = '%s %d '+format
        logging.info(formats % elems)

    def do_GET(self):
        # Parse the request
        uri = urlparse.urlparse(self.path)
        dict_query = urlparse.parse_qs(uri.query)
        path = uri.path
        
        # Check the requested endpoint
        if path not in self.dict_endpoints:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'API endpoint \'%s\' doesn\'t exist' % path }}, indent=4)
            self.wfile.write(response)
            return
        
        # Check if all endpoint parameters are present
        for param in self.dict_endpoints[path]:
            if param not in dict_query:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'missing required argument \'%s\'' % param }}, indent=4)
                self.wfile.write(response)
                return
                
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = globals()[path.split('/')[-1]](dict_query)
        self.wfile.write(response)
        return

if __name__ == '__main__':
    threading.current_thread().name = 'APIMainThread'
    my_format = '%(asctime)s;%(levelname)s;%(threadName)s;%(message)s'
    logging.basicConfig(filename='api.log', level=logging.DEBUG, format=my_format)
    logger = logging.getLogger('api')

    dict_endpoints = {
        '/api/auth' : ('username', 'password'),
        '/api/send' : ('token', 'number', 'message'),
        '/api/job' : ('token', 'id')
    }
    modem = Modem('1234')
    fifo = modem.get_fifo()
    scheduler = Scheduler(fifo)
    server = ThreadedHTTPServer(('192.168.2.9',8080), RequestHandler, dict_endpoints)
    
    # Starting the threads
    logger.info('Starting modem thread')
    modem.start()
    logger.info('Starting scheduler thread')
    scheduler.start()
    
    try:
        logger.info('Starting webserver')
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('Asking the modem thread to stop')
        modem.stop.set()
        logger.info('Asking the scheduler thread to stop')
        scheduler.stop.set()
        logger.info('Waiting for the modem thread to stop')
        modem.join()
        logger.info('Modem thread has stopped')
        logger.info('Waiting for the scheduler thread to stop')
        scheduler.join()
        logger.info('Scheduler thread has stopped')
    finally:
        pass
