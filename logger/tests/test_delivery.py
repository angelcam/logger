import time
import unittest

from unittest import mock

from ..sinks import loggly
from .support import FakeIngestServer, delivered, wait_until


class DeliveryTest(unittest.TestCase):
    """End to end checks on the two properties the batching exists for."""

    def setUp(self):
        self.server = FakeIngestServer(status=200)
        self.addCleanup(self.server.close)

        patched = mock.patch.object(loggly, 'BULK_URL', self.server.url + '{}/{}')
        patched.start()
        self.addCleanup(patched.stop)

        self.session = loggly.LogglySession('the-token', 'the-tag')

    def test_no_delay(self):
        started = time.monotonic()

        self.session.send({'message': 'alone'})
        wait_until(lambda: self.server.requests, timeout=1.0,
                   message='the message was held back')

        self.assertLess(time.monotonic() - started, 0.5,
                        'a lone message must not wait for company')

    def test_batches_burst(self):
        expected = [f'message-{i}' for i in range(5000)]

        for message in expected:
            self.session.send({'message': message})

        self.assertTrue(self.session.flush(timeout=30))

        self.assertEqual(sorted(delivered(self.server)), sorted(expected))
        self.assertLess(len(self.server.requests), 100,
                        'sent one request per message instead of batching')

    def test_batch_limit(self):
        for i in range(2000):
            self.session.send({'message': 'x' * 5000, 'index': i})

        self.assertTrue(self.session.flush(timeout=30))

        largest = max(len(body) for _, _, body in self.server.requests)
        self.assertLessEqual(largest, loggly.MAX_BATCH_SIZE)
        self.assertGreater(len(self.server.requests), 1,
                           'the payload should not have fit in one request')
