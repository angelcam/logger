import json
import unittest

from unittest import mock

from ..sinks import loggly
from .support import FakeIngestServer, delivered, wait_until


class LogglyTest(unittest.TestCase):

    def test_encode(self):
        record = {'message': 'hello'}

        line = loggly.encode(record)

        self.assertNotIn(b'\n', line)
        self.assertEqual(json.loads(line)['message'], 'hello')
        self.assertTrue(json.loads(line)['timestamp'].endswith('+00:00'))
        self.assertEqual(record, {'message': 'hello'})

    def test_delivers_ndjson(self):
        server = FakeIngestServer(status=200)
        self.addCleanup(server.close)

        with mock.patch.object(loggly, 'BULK_URL', server.url + 'bulk/{}/tag/{}/'):
            session = loggly.LogglySession('the-token', 'the-tag')
            session.send({'message': 'first'})
            session.send({'message': 'second'})

            wait_until(lambda: len(delivered(server)) == 2,
                       message='both records were not delivered')

        path, _, _ = server.requests[0]

        self.assertEqual(path, '/bulk/the-token/tag/the-tag/')
        self.assertEqual(sorted(delivered(server)), ['first', 'second'])
