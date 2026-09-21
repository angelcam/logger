import datetime
import json

from .batching import BatchingSender, NonRetryableError
from .transport import post

_ACCEPTED = 202
_RATE_LIMITED = 429


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class BetterStackSession(object):

    def __init__(self, source_token, ingesting_host, http=None, **batching):
        self._url = 'https://{}/'.format(ingesting_host)
        self._headers = {
            'Authorization': 'Bearer {}'.format(source_token),
            'Content-Type': 'application/json',
        }
        self._http = http or post
        self._sender = BatchingSender(self._deliver, **batching)

    def send(self, record):
        # Timestamp here to reflect when the record occurred, not when delivered
        stamped = dict(record)
        stamped['dt'] = _now()
        self._sender.send(stamped)

    def stop(self, timeout=3.0):
        self._sender.stop(timeout)

    def _deliver(self, records):
        body = json.dumps(records).encode('utf-8')
        status = self._http(self._url, body, self._headers)

        if status == _ACCEPTED:
            return
        if status == _RATE_LIMITED or status >= 500:
            raise IOError('Better Stack returned HTTP {}'.format(status))
        raise NonRetryableError('Better Stack rejected the request with HTTP {}'.format(status))
