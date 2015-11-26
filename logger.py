#Syslog logging module
#Use singleton "log" or class Logger
#exmaple:
#from  Logger import logger
#log.start("myAppName")
#log.set_min_level(log.INFO)

#than use singleton log or create instance of Logger
#log.log(log.INFO, "This is log message.")
#or
#if yout need to set context per class, instantiate and use class Logger
#self.log = Logger.Logger({"contextKey1", contextVal1})
#self.log.log(log.INFO, "This is log message.")
#self.log.log(log.INFO, "This is log message.", {"contextKey2": contextVal2})

# and log.info("This is log message.") works too

import json
import sys
from syslog import syslog, openlog
import datetime

#logging levels
DEBUG = 0
INFO = 1
WARN = 2
ERROR = 3

class _LoggerCore(object):

    standardizedFields = {"misc": 0, "camera_id": 0, "camera_url": 0, "user_id": 0, "email": 0, "stream_url": 0, "request_id": 0}

    def __init__(self):
        self._minLevel = DEBUG
        self._write_output = False

        self._levelDict = { DEBUG:"debug", INFO:"info", WARN:"warn", ERROR:"error", }

    def start(self, appName):
        openlog(appName)

    def debug(self, message, metaData = None):
        self.log(DEBUG, message, metaData)

    def info(self, message, metaData = None):
        self.log(INFO, message, metaData)

    def warn(self, message, metaData = None):
        self.log(WARN, message, metaData)

    def error(self, message, metaData = None):
        self.log(ERROR, message, metaData)

    #metadata = dict of other informations, standardized fields will be send as json fields other will be send as text in misc
    #value of key in metadata can be None - field will be ignored
    def log(self, level, message, metadata = None):

        if(level < self._minLevel):
            return

        levelStr = self._levelDict.get(level, None)
        if(not levelStr):
            logdata = { 'message': "Logger.log: Bad log level. Cannot log message " + message, 'level': 'info' }
            syslog(json.dumps(logdata))
            return

        #create output json
        logdata = { 'message': message, 'level': levelStr}
        if(metadata):
            for key, value in metadata.iteritems():
                if(not value):
                    continue
                if(key in self.standardizedFields):
                    logdata[key] = value
                else:
                    misc = logdata.get("misc")
                    if(misc):
                        logdata["misc"] += ", " + str(key) + ": " + str(value)
                    else:
                        logdata["misc"] = str(key) + ":" + str(value)

        syslog(json.dumps(logdata))

        #write output to stdout
        if(self._write_output):
            message = str(datetime.datetime.now()) + " (" + logdata["level"] + "): " + logdata["message"]
            if(metadata):
                for key, value in metadata.iteritems():
                    message += ", " + str(key) + ": " + str(value)
            print(message)
            sys.stdout.flush()

    #val = True / False
    def set_output_writing(self, val):
        self._write_output = val

    def set_min_level(self, level):
        self._minLevel = level

#create singleton
_loggerCore = _LoggerCore()
log = _loggerCore

class Logger(object):
    #context is dict of values
    def __init__(self, context = None):
        self._context = None
        self.set_context(context)

    #to reset context set context to None
    def set_context(self, context):
        self._context = context

    def debug(self, message, metaData = None):
        self.log(DEBUG, message, metaData)

    def info(self, message, metaData = None):
        self.log(INFO, message, metaData)

    def warn(self, message, metaData = None):
        self.log(ERROR, message, metaData)

    def error(self, message, metaData = None):
        self.log(ERROR, message, metaData)

    def log(self, level, message, metaData = None):

        #combine metadata and context
        combinedMeta = self._context.copy()
        if(metaData != None):
            combinedMeta.update(metaData)

        _loggerCore.log(level, message, combinedMeta)


