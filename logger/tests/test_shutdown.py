import contextlib
import io
import time
import unittest

from ..sinks.batching import BatchingSender
from ..sinks.betterstack import BetterStackSession
from ..sinks.loggly import LogglySession
from ..sinks.transport import post
from .support import FakeTransport


class SlowTransport(object):
    """Blocks like a real HTTP call that is not answering."""

    def __init__(self, delay):
        self.delay = delay
        self.attempts = 0

    def __call__(self, records):
        self.attempts += 1
        time.sleep(self.delay)


class StopResultTest(unittest.TestCase):
    def test_returns_true_when_drained(self):
        sender = BatchingSender(FakeTransport(), max_batch_size=1,
                                flush_interval=0.05)
        sender.send({'message': 'a'})

        self.assertTrue(sender.stop(timeout=2.0))

    def test_returns_false_when_not_drained(self):
        sender = BatchingSender(SlowTransport(5.0), max_batch_size=1,
                                flush_interval=0.05)
        sender.send({'message': 'in flight'})
        time.sleep(0.2)
        sender.send({'message': 'still queued'})

        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertFalse(sender.stop(timeout=0.3))

        self.assertIn('not delivered', err.getvalue())


class ShutdownRetryTest(unittest.TestCase):
    def test_no_retries_on_shutdown(self):
        transport = FakeTransport(fail_times=99)
        sender = BatchingSender(transport, max_batch_size=99,
                                flush_interval=60.0, max_retries=2,
                                retry_backoff=0.01)
        sender.send({'message': 'a'})

        with contextlib.redirect_stderr(io.StringIO()):
            sender.stop(timeout=2.0)

        self.assertEqual(1, transport.attempts)


class ShutdownBudgetTest(unittest.TestCase):
    def test_budget_exceeds_http_timeout(self):
        session = BetterStackSession('t', 'h.example.com', http=FakeTransport(),
                                     http_timeout=4.0)
        self.addCleanup(session.stop)

        self.assertGreater(session._sender._shutdown_timeout, 4.0)


class DefaultTransportTest(unittest.TestCase):
    def _assert_wired(self, session, timeout):
        self.addCleanup(session.stop)
        self.assertIs(post, session._http.func)
        self.assertEqual({'timeout': timeout}, session._http.keywords)

    def test_better_stack_uses_post(self):
        self._assert_wired(
            BetterStackSession('t', 'h.example.com', http_timeout=3.0), 3.0)

    def test_loggly_uses_post(self):
        self._assert_wired(LogglySession('t', 'tag', http_timeout=3.0), 3.0)
