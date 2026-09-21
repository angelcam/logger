import functools
import json

from .batching import BatchingSender, NonRetryableError
from .transport import post

_BULK_URL = 'https://logs-01.loggly.com/bulk/{}/tag/{}'
_RATE_LIMITED = 429


class LogglySession(object):

    def __init__(self, token, tag, http=None, http_timeout=5.0, **batching):
        self._url = _BULK_URL.format(token, tag)
        self._headers = {'Content-Type': 'application/json'}
        self._http = http or functools.partial(post, timeout=http_timeout)
        batching.setdefault('shutdown_timeout', http_timeout + 2.0)
        self._sender = BatchingSender(self._deliver, **batching)

    def send(self, record):
        self._sender.send(record)

    def stop(self, timeout=None):
        return self._sender.stop(timeout)

    def _deliver(self, records):
        body = '\n'.join(json.dumps(r) for r in records).encode('utf-8')
        status = self._http(self._url, body, self._headers)

        if 200 <= status < 300:
            return
        if status == _RATE_LIMITED or status >= 500:
            raise IOError('Loggly returned HTTP {}'.format(status))
        raise NonRetryableError('Loggly rejected the request with HTTP {}'.format(status))
