import contextlib
import io
import time
import unittest

from ..sinks.executor import BatchExecutor, SinkThread
from .support import RecordingPost, wait_until


class SinkThreadTest(unittest.TestCase):

    def _start(self, post, **options):
        thread = SinkThread(lambda: BatchExecutor(post, max_size=4000000, **options))
        thread.start()
        return thread

    def test_send_during_startup(self):
        post = RecordingPost()
        thread = self._start(post)
        thread.send(b'first')

        wait_until(lambda: post.records == [b'first'], message='first record lost')

    def test_daemon_thread(self):
        thread = self._start(RecordingPost())

        wait_until(lambda: thread.is_alive())
        self.assertTrue(thread.daemon, 'a non-daemon thread would hang exit')

    def test_executor_in_loop(self):
        loops = []

        def create_executor():
            import asyncio
            loops.append(asyncio.get_running_loop())
            return BatchExecutor(RecordingPost(), max_size=4000000)

        thread = SinkThread(create_executor)
        thread.start()

        wait_until(lambda: loops, message='executor was never created')
        self.assertTrue(loops[0].is_running())


class DeadLoopTest(unittest.TestCase):
    """What happens to log messages once the background loop has died."""

    class ExplodingExecutor:
        def __init__(self):
            self.sent = []

        def send(self, record):
            self.sent.append(record)

        async def run(self):
            raise RuntimeError('the loop died')

    def _start(self):
        made = []

        def create_executor():
            executor = self.ExplodingExecutor()
            made.append(executor)
            return executor

        with contextlib.redirect_stderr(io.StringIO()):
            thread = SinkThread(create_executor)
            thread.start()
            wait_until(lambda: made and not thread.is_alive())

        return thread, made[0]

    def test_reports_instead_of_dropping_in_silence(self):
        thread, executor = self._start()

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            thread.send(b'after the loop died')

        self.assertEqual(executor.sent, [],
                         'queued a record on a loop that will never run it')
        self.assertIn('logger:', stderr.getvalue(),
                      'the record was dropped without saying so')

    def test_flush_fails_fast(self):
        thread, _ = self._start()

        started = time.monotonic()
        with contextlib.redirect_stderr(io.StringIO()):
            flushed = thread.flush(timeout=5.0)

        self.assertFalse(flushed)
        self.assertLess(time.monotonic() - started, 1.0,
                        'blocked on a loop that cannot drain')
