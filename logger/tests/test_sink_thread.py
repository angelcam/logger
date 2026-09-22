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
