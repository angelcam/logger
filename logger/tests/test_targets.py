import unittest

from ..logger import ERROR, INFO, _LoggerCore


class RecordingTarget:

    def __init__(self):
        self.records = []

    def send(self, record):
        self.records.append(record)


class TargetFanoutTest(unittest.TestCase):

    def setUp(self):
        self.core = _LoggerCore()
        self.core.set_min_level(INFO)
        self.loggly = RecordingTarget()
        self.better_stack = RecordingTarget()
        self.core._loggly = self.loggly
        self.core._better_stack = self.better_stack

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

    def test_single_target(self):
        self.core._better_stack = None

        self.core.log(INFO, 'hello')

        self.assertEqual(len(self.loggly.records), 1)


class FlushAllTargetsTest(unittest.TestCase):

    class Target(RecordingTarget):
        def __init__(self, flushed=True):
            super().__init__()
            self.result = flushed
            self.calls = 0

        def flush(self, timeout=None):
            self.calls += 1
            return self.result

    def setUp(self):
        self.core = _LoggerCore()

    def test_flushes_all(self):
        self.core._loggly = self.Target()
        self.core._better_stack = self.Target()

        self.assertTrue(self.core.flush())
        self.assertEqual(self.core._loggly.calls, 1)
        self.assertEqual(self.core._better_stack.calls, 1)

    def test_reports_failure(self):
        self.core._loggly = self.Target(flushed=True)
        self.core._better_stack = self.Target(flushed=False)

        self.assertFalse(self.core.flush())
        self.assertEqual(self.core._loggly.calls, 1)

    def test_no_targets(self):
        self.assertTrue(self.core.flush())
