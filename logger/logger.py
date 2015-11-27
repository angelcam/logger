import datetime
import json
import sys
from syslog import syslog, openlog

from requests_futures.sessions import FuturesSession

# logging levels
DEBUG = 0
INFO = 1
WARN = 2
ERROR = 3


class _LoggerCore(object):

    standardized_fields = {"misc": 0, "camera_id": 0, "camera_url": 0, "user_id": 0, "email": 0, "stream_url": 0, "request_id": 0}

    def __init__(self):
        self._minLevel = DEBUG
        self._write_output = False
        self._syslog = False
        self._loggly = False

        self._levelDict = {DEBUG: "debug", INFO: "info", WARN: "warn", ERROR: "error", }

    def debug(self, message, **kwargs):
        self.log(DEBUG, message, **kwargs)

    def info(self, message, **kwargs):
        self.log(INFO, message, **kwargs)

    def warn(self, message, **kwargs):
        self.log(WARN, message, **kwargs)

    def error(self, message, **kwargs):
        self.log(ERROR, message, **kwargs)

    # kwargs = dict of other informations, standardized fields will be send as json fields other will be send as text in misc
    # value of key in metadata can be None - field will be ignored
    def log(self, level, message, **kwargs):
        if level < self._minLevel:
            return

        levelStr = self._levelDict.get(level, None)
        if not levelStr:
            logdata = {'message': "Logger.log: Bad log level. Cannot log message " + message, 'level': 'info'}
            syslog(json.dumps(logdata))
            return

        # create output json
        logdata = {'message': message, 'level': levelStr}
        if kwargs:
            for key, value in kwargs.items():
                if not value:
                    continue
                if key in self.standardized_fields:
                    # For now all std fields are strings.
                    # Any numeric field in future needs to be excluded from conversion here.
                    logdata[key] = str(value)
                else:
                    misc = logdata.get("misc", None)
                    if misc:
                        logdata["misc"] += ", " + str(key) + ": " + str(value)
                    else:
                        logdata["misc"] = str(key) + ":" + str(value)
        jsonlog = json.dumps(logdata)

        if self._syslog:
            syslog(jsonlog)

        # write output to stdout
        if self._write_output:
            message = str(datetime.datetime.now()) + " (" + logdata["level"] + "): " + logdata["message"]
            if kwargs:
                for key, value in kwargs.items():
                    message += ", " + str(key) + ": " + str(value)
            print(message)
            sys.stdout.flush()

        if self._loggly:
            self._session.post(self._loggly_url, data=jsonlog)

    # XXX backward compatibility
    def start(self, app_name):
        self.set_syslog(app_name)

    # XXX backward compatibility
    def set_output_writing(self, val):
        self.set_console(val)

    def set_console(self, enabled):
        self._write_output = enabled

    def set_syslog(self, app_name):
        self._syslog = True
        openlog(app_name)

    def set_loggly(self, token, tag):
        self._loggly = True
        self._loggly_url = 'https://logs-01.loggly.com/inputs/{}/tag/{}'.format(token, tag)
        self._session = FuturesSession()

        # https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning
        import requests.packages.urllib3
        requests.packages.urllib3.disable_warnings()

    def set_min_level(self, level):
        self._minLevel = level

# Create singleton
_loggerCore = _LoggerCore()
log = _loggerCore


class Logger(object):
    "Logger with context (a dict of values) added to all messages"
    def __init__(self, context=None):
        self.set_context(context)

    # to reset context set context to None
    def set_context(self, context):
        self._context = context

    def debug(self, message, **kwargs):
        self.log(DEBUG, message, **kwargs)

    def info(self, message, **kwargs):
        self.log(INFO, message, **kwargs)

    def warn(self, message, **kwargs):
        self.log(ERROR, message, **kwargs)

    def error(self, message, **kwargs):
        self.log(ERROR, message, **kwargs)

    def log(self, level, message, **kwargs):
        # combine kwargs and context
        if not kwargs:
            kwargs = {}
        if self._context:
            kwargs.update(self._context)
        _loggerCore.log(level, message, **kwargs)
