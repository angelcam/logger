import os
import subprocess
import sys
import textwrap
import threading
import unittest

from ..logger import _loggerCore
from .support import FakeHttp


class ReconfigureTest(unittest.TestCase):
    """Replacing a target must retire the previous one: its worker thread and shutdown hook outlive the core's reference."""

    def tearDown(self):
        for sink in (_loggerCore._loggly, _loggerCore._better_stack):
            if sink:
                sink.stop()
        _loggerCore._loggly = None
        _loggerCore._better_stack = None

    def _set_better_stack(self, token):
        _loggerCore.set_better_stack(
            token, 'h.example.com', http=FakeHttp(202),
            max_batch_size=1, flush_interval=0.05)

    def _set_loggly(self, token):
        _loggerCore.set_loggly(
            token, 'tag', http=FakeHttp(200),
            max_batch_size=1, flush_interval=0.05)

    def test_better_stack_no_thread_leak(self):
        before = threading.active_count()
        for i in range(4):
            self._set_better_stack('t%d' % i)
        self.assertEqual(before + 1, threading.active_count())

    def test_loggly_no_thread_leak(self):
        before = threading.active_count()
        for i in range(4):
            self._set_loggly('t%d' % i)
        self.assertEqual(before + 1, threading.active_count())

    def test_replaced_target_is_stopped(self):
        self._set_better_stack('first')
        retired = _loggerCore._better_stack
        self._set_better_stack('second')

        self.assertFalse(retired._sender._worker.is_alive())

    def test_only_live_target_delivers(self):
        script = textwrap.dedent('''
            import sys, json
            sys.path.insert(0, %r)
            from logger import log

            def make(name):
                def http(url, body, headers):
                    print('DELIVERED BY ' + name)
                    return 202
                return http

            for i in range(3):
                log.set_better_stack('tok', 'h.example.com', http=make('session-%%d' %% i),
                                     max_batch_size=99, flush_interval=60.0)
            log.info('still queued at exit')
        ''' % os.getcwd())

        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True, text=True, timeout=30)

        self.assertEqual('DELIVERED BY session-2', result.stdout.strip())
