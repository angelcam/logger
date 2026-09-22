import asyncio
import contextlib
import io
import unittest

from unittest import mock

from ..sinks import executor as executor_module
from ..sinks.executor import BatchExecutor
from .support import (ALWAYS, BlockingPost, FailingPost, RecordingPost,
                      RejectingPost, SlowPost, TimingOutPost,
                      eventually)


class ExecutorTestCase(unittest.IsolatedAsyncioTestCase):
    """Shared setup only; the cases below hold the tests."""

    def setUp(self):
        patched = mock.patch.object(executor_module, 'RETRY_BACKOFF', 0.01)
        patched.start()
        self.addCleanup(patched.stop)

    def _start(self, post, **options):
        executor = BatchExecutor(post, max_size=4000000, **options)
        running = asyncio.ensure_future(executor.run())
        self.addCleanup(running.cancel)
        return executor


class BatchingTest(ExecutorTestCase):

    async def test_ndjson_body(self):
        post = RecordingPost()
        executor = self._start(post)

        executor.send(b'{"m":"a"}')
        executor.send(b'{"m":"b"}')

        await eventually(lambda: len(post.records) == 2)
        self.assertEqual(sorted(post.records), [b'{"m":"a"}', b'{"m":"b"}'])

    async def test_max_tasks(self):
        post = BlockingPost()
        executor = self._start(post, max_tasks=3)

        for _ in range(10):
            executor.send(b'x')
            await asyncio.sleep(0.01)

        await eventually(lambda: post.in_flight == 3)
        await asyncio.sleep(0.05)
        self.assertEqual(post.in_flight, 3, 'exceeded max_tasks')


class NoDropByDefaultTest(ExecutorTestCase):

    async def test_slow_sender(self):
        post = SlowPost(delay=0.02)
        executor = self._start(post, max_tasks=1)
        expected = [b'%d' % i for i in range(2000)]

        for record in expected:
            executor.send(record)

        await eventually(lambda: len(post.records) == len(expected), timeout=10)
        self.assertEqual(sorted(post.records), sorted(expected))
        self.assertEqual(executor.dropped, 0)


class OptionalDroppingTest(ExecutorTestCase):

    async def test_unbounded_by_default(self):
        executor = self._start(BlockingPost(), max_tasks=1)

        for _ in range(5000):
            executor.send(b'x')

        await asyncio.sleep(0.05)
        self.assertEqual(executor.dropped, 0)

    async def test_drops_when_full(self):
        post = BlockingPost()
        executor = self._start(post, max_tasks=1, max_queue_size=5)
        executor.send(b'first')
        await eventually(lambda: post.in_flight == 1)

        for i in range(20):
            executor.send(b'%d' % i)
        await asyncio.sleep(0.05)

        self.assertEqual(executor.queue_size, 5)
        self.assertEqual(executor.dropped, 15)


class ReportingTest(ExecutorTestCase):

    async def test_reports_drops(self):
        post = BlockingPost()
        executor = self._start(post, max_tasks=1, max_queue_size=1)

        executor.send(b'first')
        await eventually(lambda: post.in_flight == 1)

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            for _ in range(10):
                executor.send(b'x')
            await asyncio.sleep(0.05)

        report = stderr.getvalue()
        self.assertIn('queue is full', report)
        self.assertIn('dropped', report)
        self.assertEqual(len(report.strip().splitlines()), 1)
        self.assertEqual(executor.dropped, 9)

    async def test_reports_failure(self):
        post = FailingPost(failures=ALWAYS)

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            executor = self._start(post)
            executor.send(b'lost')
            executor.send(b'lost too')
            await eventually(lambda: executor.lost == 2)

        report = stderr.getvalue()
        self.assertIn('transport is down', report)
        self.assertIn('2 records', report)

    async def test_survives_failure(self):
        post = RejectingPost(failures=1)

        with contextlib.redirect_stderr(io.StringIO()):
            executor = self._start(post, max_tasks=1)
            executor.send(b'lost')
            await eventually(lambda: executor.lost == 1)

            executor.send(b'delivered')
            await eventually(lambda: post.records == [b'delivered'])

    async def test_rate_limits_failures(self):
        post = FailingPost(failures=ALWAYS)

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            executor = self._start(post, max_tasks=1)
            for i in range(10):
                executor.send(b'%d' % i)
                await eventually(lambda n=i: executor.lost == n + 1)

        report = stderr.getvalue()
        # a target that is down must not bury stderr under repeated tracebacks
        self.assertEqual(report.count('logger: failed to deliver'), 1)
        self.assertLessEqual(report.count('Traceback'), 1)

    async def test_reports_total_lost(self):
        post = FailingPost(failures=ALWAYS)

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            executor = self._start(post, max_tasks=1)
            executor.send(b'a')
            await eventually(lambda: executor.lost == 1)
            executor.send(b'b')
            await eventually(lambda: executor.lost == 2)

        self.assertIn('1 records', stderr.getvalue())


class RetryTest(ExecutorTestCase):

    async def test_retries_a_transient_failure(self):
        post = FailingPost(failures=2)
        executor = self._start(post)

        executor.send(b'a')

        await eventually(lambda: post.records == [b'a'])
        self.assertEqual(post.attempts, 3)
        self.assertEqual(executor.lost, 0)

    async def test_gives_up_after_the_last_attempt(self):
        post = FailingPost(failures=99)

        with contextlib.redirect_stderr(io.StringIO()):
            executor = self._start(post)
            executor.send(b'a')
            await eventually(lambda: executor.lost == 1)

        self.assertEqual(post.attempts, executor_module.SEND_ATTEMPTS)

    async def test_does_not_retry_a_permanent_failure(self):
        post = RejectingPost()

        with contextlib.redirect_stderr(io.StringIO()):
            executor = self._start(post)
            executor.send(b'a')
            await eventually(lambda: executor.lost == 1)

        self.assertEqual(post.attempts, 1,
                         'retried a failure that can never succeed')

    async def test_does_not_retry_a_timeout(self):
        post = TimingOutPost()

        with contextlib.redirect_stderr(io.StringIO()):
            executor = self._start(post)
            executor.send(b'a')
            await eventually(lambda: executor.lost == 1)

        self.assertEqual(post.attempts, 1, 'retried an ambiguous failure')
