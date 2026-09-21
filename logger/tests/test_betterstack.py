import contextlib
import io
import json
import time
import unittest

from ..sinks.betterstack import BetterStackSession
from .support import FakeHttp


class BetterStackPayloadTest(unittest.TestCase):
    def test_posts_json_array(self):
        http = FakeHttp()
        session = BetterStackSession(
            'src-token', 's123.eu.betterstackdata.com',
            http=http, max_batch_size=2, flush_interval=0.05)
        self.addCleanup(session.stop)

        session.send({'message': 'a', 'level': 'info'})
        session.send({'message': 'b', 'level': 'error'})

        self.assertTrue(http.wait_for_calls(1), 'nothing was posted')
        url, body, headers = http.calls[0]

        self.assertEqual('https://s123.eu.betterstackdata.com/', url)
        self.assertEqual('Bearer src-token', headers['Authorization'])
        self.assertEqual('application/json', headers['Content-Type'])

        payload = json.loads(body.decode('utf-8'))
        self.assertEqual(['a', 'b'], [r['message'] for r in payload])
        self.assertEqual(['info', 'error'], [r['level'] for r in payload])

    def test_stamps_dt_at_log_time(self):
        http = FakeHttp()
        session = BetterStackSession(
            'src-token', 'host.example.com',
            http=http, max_batch_size=2, flush_interval=60.0)
        self.addCleanup(session.stop)

        session.send({'message': 'first'})
        time.sleep(0.05)
        session.send({'message': 'second'})

        self.assertTrue(http.wait_for_calls(1), 'nothing was posted')
        payload = json.loads(http.calls[0][1].decode('utf-8'))

        self.assertIn('dt', payload[0])
        self.assertNotEqual(
            payload[0]['dt'], payload[1]['dt'],
            'both records share a timestamp, so dt is stamped at flush time')

    def test_does_not_mutate_record(self):
        http = FakeHttp()
        session = BetterStackSession(
            'src-token', 'host.example.com',
            http=http, max_batch_size=1, flush_interval=0.05)
        self.addCleanup(session.stop)

        record = {'message': 'a'}
        session.send(record)

        self.assertTrue(http.wait_for_calls(1))
        self.assertEqual({'message': 'a'}, record)


class BetterStackErrorTest(unittest.TestCase):
    def test_rejected_token_disables_target(self):
        http = FakeHttp(status=403)
        session = BetterStackSession(
            'bad-token', 'host.example.com',
            http=http, max_batch_size=1, flush_interval=0.05,
            max_retries=2, retry_backoff=0.01)
        self.addCleanup(session.stop)

        with contextlib.redirect_stderr(io.StringIO()):
            session.send({'message': 'a'})
            self.assertTrue(http.wait_for_calls(1))
            for _ in range(3):
                session.send({'message': 'more'})
            self.assertFalse(http.wait_for_calls(2, timeout=0.3))

        self.assertEqual(1, len(http.calls))

    def test_server_error_is_retried(self):
        http = FakeHttp(status=500)
        session = BetterStackSession(
            'src-token', 'host.example.com',
            http=http, max_batch_size=1, flush_interval=0.05,
            max_retries=2, retry_backoff=0.01)
        self.addCleanup(session.stop)

        with contextlib.redirect_stderr(io.StringIO()):
            session.send({'message': 'a'})
            self.assertTrue(http.wait_for_calls(3))

        self.assertEqual(3, len(http.calls))
