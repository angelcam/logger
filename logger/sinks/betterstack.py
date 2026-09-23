import json

from . import utcnow
from .base import Sink

INGEST_URL = 'https://{}/'
MAX_BATCH_SIZE = 10000000


def headers(source_token):
    return {
        'authorization': f'Bearer {source_token}',
        'content-type': 'application/x-ndjson',
    }


def encode(record):
    """Render a log record as one NDJSON line with 'dt' as the event time."""
    return json.dumps({'dt': utcnow(), **record}).encode('utf-8')


class BetterStackSession(Sink):
    def __init__(self, source_token, ingesting_host, **options):
        super().__init__(INGEST_URL.format(ingesting_host),
                         headers(source_token), encode, MAX_BATCH_SIZE,
                         **options)
