import json
import unittest

from unittest import mock

from ..sinks import loggly
from .support import FakeIngestServer, delivered, wait_until


class LogglyEncodingTest(unittest.TestCase):

    def test_json_line(self):
        line = loggly.encode({'message': 'hello', 'level': 'info'})

        self.assertNotIn(b'\n', line)
        self.assertEqual(json.loads(line)['message'], 'hello')

    def test_timestamp(self):
        record = json.loads(loggly.encode({'message': 'hello'}))

        self.assertIn('timestamp', record)
        self.assertTrue(record['timestamp'].endswith('+00:00'),
                        'the timestamp must be UTC')

    def test_does_not_mutate(self):
        record = {'message': 'hello'}

        loggly.encode(record)

        self.assertEqual(record, {'message': 'hello'})

    def test_bulk_url(self):
        url = loggly.BULK_URL.format('the-token', 'the-tag')

        self.assertEqual(
            url, 'https://logs-01.loggly.com/bulk/the-token/tag/the-tag/')

    def test_batch_limit(self):
        self.assertLessEqual(loggly.MAX_BATCH_SIZE, 4 * 1024 * 1024)


class LogglySessionTest(unittest.TestCase):

    def test_delivers_ndjson(self):
        server = FakeIngestServer(status=200)
        self.addCleanup(server.close)

        with mock.patch.object(loggly, 'BULK_URL', server.url + 'bulk/{}/tag/{}/'):
            session = loggly.LogglySession('the-token', 'the-tag')
            session.send({'message': 'first'})
            session.send({'message': 'second'})

            wait_until(lambda: len(delivered(server)) == 2,
                       message='both records were not delivered')

        path, headers, _ = server.requests[0]

        self.assertEqual(path, '/bulk/the-token/tag/the-tag/')
        self.assertEqual(sorted(delivered(server)), ['first', 'second'])
