import unittest

from ..logger import ERROR, INFO, _LoggerCore


class RecordingTarget:

    def __init__(self, flushed=True):
        self.records = []
        self.flushed = flushed
        self.flushes = 0

    def send(self, record):
        self.records.append(record)

    def flush(self, timeout=None):
        self.flushes += 1
        return self.flushed


class TargetsTest(unittest.TestCase):

    def setUp(self):
        self.core = _LoggerCore()
        self.core.set_min_level(INFO)
        self.loggly = self.core._loggly = RecordingTarget()
        self.better_stack = self.core._better_stack = RecordingTarget()

    def test_both_targets(self):
        self.core.log(INFO, 'hello', camera_id=7)

        for target in (self.loggly, self.better_stack):
            self.assertEqual(len(target.records), 1)
            self.assertEqual(target.records[0]['message'], 'hello')
            self.assertEqual(target.records[0]['camera_id'], '7')

    def test_min_level(self):
        self.core.set_min_level(ERROR)

        self.core.log(INFO, 'ignored')

        self.assertEqual(self.loggly.records, [])
        self.assertEqual(self.better_stack.records, [])

    def test_flush_all(self):
        self.assertTrue(self.core.flush())

        self.better_stack.flushed = False

        self.assertFalse(self.core.flush())
        self.assertEqual(self.loggly.flushes, 2)
        self.assertEqual(self.better_stack.flushes, 2)
