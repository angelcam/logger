import contextlib
import io
import json
import unittest

from ..sinks.loggly import LogglySession
from .support import FakeHttp


class LogglyPayloadTest(unittest.TestCase):
    def test_posts_ndjson_to_bulk_endpoint(self):
        http = FakeHttp(status=200)
        session = LogglySession(
            'tok', 'app-prod', http=http, max_batch_size=2, flush_interval=0.05)
        self.addCleanup(session.stop)

        session.send({'message': 'a', 'level': 'info'})
        session.send({'message': 'b', 'level': 'error'})

        self.assertTrue(http.wait_for_calls(1), 'nothing was posted')
        url, body, headers = http.calls[0]

        self.assertEqual('https://logs-01.loggly.com/bulk/tok/tag/app-prod', url)
        self.assertEqual('application/json', headers['Content-Type'])

        lines = body.decode('utf-8').split('\n')
        self.assertEqual(['a', 'b'], [json.loads(line)['message'] for line in lines])

    def test_one_request_per_batch(self):
        http = FakeHttp(status=200)
        session = LogglySession(
            'tok', 'app-prod', http=http, max_batch_size=5, flush_interval=0.05)
        self.addCleanup(session.stop)

        for i in range(5):
            session.send({'message': 'm%d' % i})

        self.assertTrue(http.wait_for_calls(1))
        self.assertFalse(http.wait_for_calls(2, timeout=0.3))
        self.assertEqual(1, len(http.calls))


class LogglyErrorTest(unittest.TestCase):
    def test_rejected_token_disables_target(self):
        http = FakeHttp(status=403)
        session = LogglySession(
            'bad', 'app-prod', http=http, max_batch_size=1,
            flush_interval=0.05, max_retries=2, retry_backoff=0.01)
        self.addCleanup(session.stop)

        with contextlib.redirect_stderr(io.StringIO()):
            session.send({'message': 'a'})
            self.assertTrue(http.wait_for_calls(1))
            session.send({'message': 'more'})
            self.assertFalse(http.wait_for_calls(2, timeout=0.3))

        self.assertEqual(1, len(http.calls))

    def test_server_error_is_retried(self):
        http = FakeHttp(status=503)
        session = LogglySession(
            'tok', 'app-prod', http=http, max_batch_size=1,
            flush_interval=0.05, max_retries=2, retry_backoff=0.01)
        self.addCleanup(session.stop)

        with contextlib.redirect_stderr(io.StringIO()):
            session.send({'message': 'a'})
            self.assertTrue(http.wait_for_calls(3))

        self.assertEqual(3, len(http.calls))
