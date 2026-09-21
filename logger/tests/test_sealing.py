import contextlib
import io
import threading
import unittest

from ..sinks.batching import BatchingSender
from .support import FakeTransport


class SealingTest(unittest.TestCase):
    def test_send_after_stop_is_counted(self):
        sender = BatchingSender(FakeTransport(), max_batch_size=1,
                                flush_interval=0.05)
        sender.stop()

        with contextlib.redirect_stderr(io.StringIO()):
            sender.send({'message': 'too late'})

        self.assertEqual(0, sender.queue_size)
        self.assertEqual(1, sender.dropped_count)

    def test_no_record_stranded_on_stop(self):
        for _ in range(50):
            transport = FakeTransport()
            sender = BatchingSender(transport, max_batch_size=50,
                                    flush_interval=0.05)

            stopped = []
            thread = threading.Thread(
                target=lambda: stopped.append(sender.stop(timeout=2.0)))
            thread.start()
            with contextlib.redirect_stderr(io.StringIO()):
                for i in range(5):
                    sender.send({'message': 'm%d' % i})
            thread.join()

            self.assertEqual(0, sender.queue_size)
            delivered = sum(len(b) for b in transport.batches)
            self.assertEqual(5, delivered + sender.dropped_count)
