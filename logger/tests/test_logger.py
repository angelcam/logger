from contextlib import contextmanager
import six
import sys
import unittest

from ..logger import log, INFO, Logger

@contextmanager
def capture(command, *args, **kwargs):
    out, sys.stdout = sys.stdout, six.StringIO()
    command(*args, **kwargs)
    sys.stdout.seek(0)
    yield sys.stdout.read()
    sys.stdout = out

class LoggerTest(unittest.TestCase):
    def setUp(self):
        log.set_console(True)
        log.set_min_level(INFO)

    def test_plain(self):
        out, sys.stdout = sys.stdout, six.StringIO()

        log.debug('Debug message')
        log.info('Info message')

        sys.stdout.seek(0)
        output = sys.stdout.read()
        sys.stdout = out

        assert 'Info message' in output
        assert 'Debug message' not in output

    def test_context(self):
        clog = Logger(camera_id=1)

        out, sys.stdout = sys.stdout, six.StringIO()

        clog.info('Info message')

        sys.stdout.seek(0)
        output = sys.stdout.read()
        sys.stdout = out

        assert 'camera_id: 1' in output

        clog.set_context(user_id=1)

        out, sys.stdout = sys.stdout, six.StringIO()

        clog.info('Info message')

        sys.stdout.seek(0)
        output = sys.stdout.read()
        sys.stdout = out
        assert 'camera_id: 1' not in output
        assert 'user_id: 1' in output

