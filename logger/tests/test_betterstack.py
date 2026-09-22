import json
import unittest

from unittest import mock

from ..sinks import betterstack
from .support import FakeIngestServer, delivered, wait_until


class BetterStackEncodingTest(unittest.TestCase):

    def test_json_line(self):
        line = betterstack.encode({'message': 'hello', 'level': 'info'})

        self.assertNotIn(b'\n', line)
        self.assertEqual(json.loads(line)['message'], 'hello')

    def test_dt_field(self):
        record = json.loads(betterstack.encode({'message': 'hello'}))

        self.assertIn('dt', record)
        self.assertTrue(record['dt'].endswith('+00:00'),
                        'the timestamp must be UTC')

    def test_does_not_mutate(self):
        record = {'message': 'hello'}

        betterstack.encode(record)

        self.assertEqual(record, {'message': 'hello'})

    def test_ingest_url(self):
        url = betterstack.INGEST_URL.format('s123456.eu-nbg-2.betterstackdata.com')

        self.assertEqual(url, 'https://s123456.eu-nbg-2.betterstackdata.com/')

    def test_bearer_token(self):
        headers = betterstack.headers('the-token')

        self.assertEqual(headers['authorization'], 'Bearer the-token')
        self.assertEqual(headers['content-type'], 'application/x-ndjson')

    def test_batch_limit(self):
        self.assertLessEqual(betterstack.MAX_BATCH_SIZE, 10 * 1024 * 1024)


class BetterStackSessionTest(unittest.TestCase):

    def test_delivers_ndjson(self):
        server = FakeIngestServer(status=202)
        self.addCleanup(server.close)

        with mock.patch.object(betterstack, 'INGEST_URL', server.url + '{}'):
            session = betterstack.BetterStackSession('the-token', 'ignored-host')
            session.send({'message': 'first'})
            session.send({'message': 'second'})

            wait_until(lambda: len(delivered(server)) == 2,
                       message='both records were not delivered')

        path, headers, _ = server.requests[0]

        self.assertEqual(headers['authorization'], 'Bearer the-token')
        self.assertEqual(headers['content-type'], 'application/x-ndjson')
        self.assertEqual(sorted(delivered(server)), ['first', 'second'])
