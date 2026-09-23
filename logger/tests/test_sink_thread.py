import contextlib
import io
import time
import unittest

from ..sinks.executor import BatchExecutor, SinkThread
from .support import RecordingPost, wait_until


class SinkThreadTest(unittest.TestCase):

    def test_send_on_startup(self):
        post = RecordingPost()
        thread = SinkThread(lambda: BatchExecutor(post, max_size=4000000))
        thread.start()
        thread.send(b'first')

        wait_until(lambda: post.records == [b'first'], message='first record lost')


class DeadLoopTest(unittest.TestCase):
    """What happens to log messages once the background loop has died."""

    class ExplodingExecutor:
        def __init__(self):
            self.sent = []

        def send(self, record):
            self.sent.append(record)

        async def run(self):
            raise RuntimeError('the loop died')

    def test_dead_loop(self):
        executor = self.ExplodingExecutor()

        with contextlib.redirect_stderr(io.StringIO()):
            thread = SinkThread(lambda: executor)
            thread.start()
            wait_until(lambda: not thread.is_alive())

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            thread.send(b'after the loop died')
            started = time.monotonic()
            flushed = thread.flush(timeout=5.0)

        self.assertEqual(executor.sent, [],
                         'queued a record on a loop that will never run it')
        self.assertIn('logger:', stderr.getvalue(),
                      'the record was dropped without saying so')
        self.assertFalse(flushed)
        self.assertLess(time.monotonic() - started, 1.0,
                        'blocked on a loop that cannot drain')
