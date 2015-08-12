# coding : utf-8
import BaseHTTPServer
from SocketServer import ThreadingMixIn
import urlparse
import phonenumbers
import json
import hashlib
import datetime
import threading
import Queue

from sms import *
from user import *
from modem import *
from global_var import *

# Define the API endpoints here
def auth(dict_query):
    param_username = dict_query['username'][0]
    param_password = dict_query['password'][0]
    sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH)
    if debug: User._connection.debug = True 
    # We need to create the tables
    User.createTable(ifNotExists=True)
    
    # We need to get the user object
    user_object = User.select(User.q.login == param_username)
    try:
        db_user = user_object.getOne()
        pbdkf2_password = hashlib.pbkdf2_hmac('sha256', param_password, db_user.salt, 100000)
        # Password is correct
        if db_user.password == pbdkf2_password:
            # Check if a valid token is present in DB
            if db_user.token and db_user.expirationDate > datetime.datetime.now():
                pass
            else:
                db_user.token = binascii.hexlify(os.urandom(16))
            db_user.expirationDate = datetime.datetime.now() + datetime.timedelta(hours=24)
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
    sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('sqlite://'+DB_PATH)
    if debug: User._connection.debug = True 
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
    formated_number = phonenumbers.format_number(obj_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    # Retrieve the token in database
    user_object = User.select(User.q.token == param_token)
    try:
        db_user = user_object.getOne()
        if db_user.expirationDate > datetime.datetime.now():
            # Token is valid
            try:
                temp_fifo = Queue.Queue(1)
                new_sms = SMS(formated_number, param_message, temp_fifo)
                fifo.put(new_sms, True, 5)
                fifo.join()
                modem_response = temp_fifo.get(True, 5)
                temp_fifo.task_done()
                response = json.dumps({'response' : {'status' : 'success'}}, indent=4)
            except Full as error:
                response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'modem thread didn\'t respond'}}, indent=4)
        else:
            response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'expired token'}}, indent=4)

    except sqlobject.SQLObjectIntegrityError as error:
        # We should not have more than one object returned
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'SQLi detected'}}, indent=4)
    except sqlobject.SQLObjectNotFound as error:
        response = json.dumps({'response' : {'status' : 'failed', 'reason' : 'invalid token'}}, indent=4)

    return response

# WebServer classes
class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
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
                self.send_response(404)
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
    dict_endpoints = {
        '/api/auth' : ('username', 'password'),
        '/api/send' : ('token', 'number', 'message'),
        '/api/jobs' : ('token', 'id')
    }

    modem = Modem('1234')
    fifo = modem.getFifo()
    modem.start()
    server = ThreadedHTTPServer(('192.168.2.9',8080), RequestHandler, dict_endpoints)
    try:
        if debug: print 'Starting API web server'
        server.serve_forever()
    except KeyboardInterrupt:
        if debug: print 'Stopping modem'
        modem.stop.set()
        if debug: print 'Waiting for modem thread to terminate'
        modem.join()
    finally:
        pass
