import requests.packages.urllib3

from requests_futures.sessions import FuturesSession


class LogglySession(object):
    """
    LogglySession for Python 2.7.x
    """

    def __init__(self, token, tag):
        self.__url = 'https://logs-01.loggly.com/inputs/{}/tag/{}'.format(token, tag)
        self.__session = FuturesSession()

        # https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning
        requests.packages.urllib3.disable_warnings()

    def send(self, data):
        self.__session.post(self.__url, data=data)
