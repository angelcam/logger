import json

from . import utcnow
from .base import Sink

BULK_URL = 'https://logs-01.loggly.com/bulk/{}/tag/{}/'
MAX_BATCH_SIZE = 4000000

HEADERS = {
    'content-type': 'text/plain',
}


def encode(record):
    """Render a log record as NDJSON with its own timestamp."""
    return json.dumps({'timestamp': utcnow(), **record}).encode('utf-8')


class LogglySession(Sink):
    def __init__(self, token, tag, **options):
        super().__init__(BULK_URL.format(token, tag), HEADERS, encode,
                         MAX_BATCH_SIZE, **options)
