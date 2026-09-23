import json
import unittest

from unittest import mock

from ..sinks import betterstack
from .support import FakeIngestServer, delivered, wait_until


class BetterStackTest(unittest.TestCase):

    def test_encode(self):
        record = {'message': 'hello'}

        line = betterstack.encode(record)

        self.assertNotIn(b'\n', line)
        self.assertEqual(json.loads(line)['message'], 'hello')
        self.assertTrue(json.loads(line)['dt'].endswith('+00:00'))
        self.assertEqual(record, {'message': 'hello'})

    def test_delivers_ndjson(self):
        server = FakeIngestServer(status=202)
        self.addCleanup(server.close)

        with mock.patch.object(betterstack, 'INGEST_URL', server.url + '{}'):
            session = betterstack.BetterStackSession('the-token', 'ignored-host')
            session.send({'message': 'first'})
            session.send({'message': 'second'})

            wait_until(lambda: len(delivered(server)) == 2,
                       message='both records were not delivered')

        _, headers, _ = server.requests[0]

        self.assertEqual(headers['authorization'], 'Bearer the-token')
        self.assertEqual(headers['content-type'], 'application/x-ndjson')
        self.assertEqual(sorted(delivered(server)), ['first', 'second'])
