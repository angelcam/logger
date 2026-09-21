import contextlib
import io
import os
import subprocess
import sys
import textwrap
import time
import unittest

from ..sinks.batching import BatchingSender, NonRetryableError
from .support import BlockingTransport, FakeTransport


@contextlib.contextmanager
def quiet_stderr():
    with contextlib.redirect_stderr(io.StringIO()) as captured:
        yield captured


class BatchingSenderSizeTest(unittest.TestCase):
    def test_flushes_when_batch_is_full(self):
        transport = FakeTransport()
        sender = BatchingSender(transport, max_batch_size=3, flush_interval=60.0)
        self.addCleanup(sender.stop)

        for i in range(3):
            sender.send({'message': 'm%d' % i})

        self.assertTrue(transport.wait_for_batches(1), 'no batch was sent')
        self.assertEqual(
            [{'message': 'm0'}, {'message': 'm1'}, {'message': 'm2'}],
            transport.batches[0])


class BatchingSenderIntervalTest(unittest.TestCase):
    def test_flushes_partial_batch_on_interval(self):
        transport = FakeTransport()
        sender = BatchingSender(
            transport, max_batch_size=100, flush_interval=0.05)
        self.addCleanup(sender.stop)

        sender.send({'message': 'a'})
        sender.send({'message': 'b'})

        self.assertTrue(transport.wait_for_batches(1), 'partial batch never flushed')
        self.assertEqual([{'message': 'a'}, {'message': 'b'}], transport.batches[0])


class BatchingSenderRetryTest(unittest.TestCase):
    def test_retries_until_accepted(self):
        transport = FakeTransport(fail_times=2)
        sender = BatchingSender(
            transport, max_batch_size=1, flush_interval=0.05,
            max_retries=2, retry_backoff=0.01)
        self.addCleanup(sender.stop)

        sender.send({'message': 'a'})

        self.assertTrue(transport.wait_for_batches(1), 'batch was never delivered')
        self.assertEqual([{'message': 'a'}], transport.batches[0])
        self.assertEqual(3, transport.attempts)

    def test_drops_batch_after_max_retries(self):
        transport = FakeTransport(fail_times=3)
        sender = BatchingSender(
            transport, max_batch_size=1, flush_interval=0.05,
            max_retries=2, retry_backoff=0.01)
        self.addCleanup(sender.stop)

        with quiet_stderr():
            sender.send({'message': 'doomed'})
            self.assertFalse(transport.wait_for_batches(1, timeout=0.3))

        sender.send({'message': 'later'})

        self.assertTrue(transport.wait_for_batches(1), 'worker died with the batch')
        self.assertEqual([{'message': 'later'}], transport.batches[0])


class BatchingSenderNonRetryableTest(unittest.TestCase):
    def test_does_not_retry_fatal_error(self):
        transport = FakeTransport(
            fail_times=99, error=NonRetryableError('invalid source token'))
        sender = BatchingSender(
            transport, max_batch_size=1, flush_interval=0.05,
            max_retries=2, retry_backoff=0.01)
        self.addCleanup(sender.stop)

        with quiet_stderr():
            sender.send({'message': 'a'})
            self.assertFalse(transport.wait_for_batches(1, timeout=0.3))

        self.assertEqual(1, transport.attempts)

    def test_disables_after_fatal_error(self):
        transport = FakeTransport(
            fail_times=99, error=NonRetryableError('invalid source token'))
        sender = BatchingSender(
            transport, max_batch_size=1, flush_interval=0.05,
            max_retries=2, retry_backoff=0.01)
        self.addCleanup(sender.stop)

        with quiet_stderr():
            sender.send({'message': 'a'})
            self.assertFalse(transport.wait_for_batches(1, timeout=0.3))
            for _ in range(5):
                sender.send({'message': 'ignored'})
            self.assertFalse(transport.wait_for_batches(1, timeout=0.3))

        self.assertEqual(1, transport.attempts)


class BatchingSenderBackpressureTest(unittest.TestCase):
    def test_send_never_blocks(self):
        transport = BlockingTransport()
        sender = BatchingSender(
            transport, max_batch_size=1, flush_interval=0.05, max_queue_size=2)
        self.addCleanup(sender.stop)
        self.addCleanup(transport.release.set)

        sender.send({'message': 'in-flight'})
        self.assertTrue(transport.entered.wait(1.0), 'worker never started a delivery')

        with quiet_stderr():
            for i in range(5):
                sender.send({'message': 'q%d' % i})

        self.assertEqual(2, sender.queue_size)

    def test_drops_oldest_on_overflow(self):
        transport = BlockingTransport()
        sender = BatchingSender(
            transport, max_batch_size=1, flush_interval=0.05, max_queue_size=2)
        self.addCleanup(sender.stop)

        sender.send({'message': 'in-flight'})
        self.assertTrue(transport.entered.wait(1.0), 'worker never started a delivery')

        with quiet_stderr():
            for i in range(5):
                sender.send({'message': 'q%d' % i})

        self.assertEqual(3, sender.dropped_count)
        transport.release.set()

        deadline = time.time() + 2.0
        while time.time() < deadline and len(transport.delivered_messages()) < 3:
            time.sleep(0.01)

        self.assertEqual(['in-flight', 'q3', 'q4'], transport.delivered_messages())


class BatchingSenderShutdownTest(unittest.TestCase):
    def test_stop_flushes_queue(self):
        transport = FakeTransport()
        sender = BatchingSender(
            transport, max_batch_size=1000, flush_interval=60.0)

        sender.send({'message': 'pending'})
        sender.stop()

        self.assertEqual([[{'message': 'pending'}]], transport.batches)

    def test_flushes_on_process_exit(self):
        script = textwrap.dedent('''
            import sys
            sys.path.insert(0, %r)
            from logger.sinks.batching import BatchingSender

            def transport(records):
                print('DELIVERED:' + ','.join(r['message'] for r in records))

            sender = BatchingSender(
                transport, max_batch_size=1000, flush_interval=60.0)
            sender.send({'message': 'before-exit'})
        ''' % os.getcwd())

        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True, text=True, timeout=30)

        self.assertIn('DELIVERED:before-exit', result.stdout)
