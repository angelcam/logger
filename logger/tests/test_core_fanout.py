import json
import unittest

from ..logger import _loggerCore, INFO
from .support import FakeHttp


class CoreFanoutTest(unittest.TestCase):
    def setUp(self):
        _loggerCore.set_min_level(INFO)
        _loggerCore.set_console(False)

    def tearDown(self):
        for sink in (_loggerCore._loggly, _loggerCore._better_stack):
            if sink:
                sink.stop()
        _loggerCore._loggly = None
        _loggerCore._better_stack = None

    def test_reaches_both_targets(self):
        loggly_http = FakeHttp(status=200)
        better_stack_http = FakeHttp(status=202)

        _loggerCore.set_loggly(
            'tok', 'app-prod', http=loggly_http,
            max_batch_size=1, flush_interval=0.05)
        _loggerCore.set_better_stack(
            'src', 'host.example.com', http=better_stack_http,
            max_batch_size=1, flush_interval=0.05)

        _loggerCore.info('hello', camera_id=7)

        self.assertTrue(loggly_http.wait_for_calls(1), 'Loggly got nothing')
        self.assertTrue(better_stack_http.wait_for_calls(1), 'Better Stack got nothing')

    def test_sends_structured_fields(self):
        http = FakeHttp(status=202)
        _loggerCore.set_better_stack(
            'src', 'host.example.com', http=http,
            max_batch_size=1, flush_interval=0.05)

        _loggerCore.info('hello', camera_id=7, whatever='x')

        self.assertTrue(http.wait_for_calls(1))
        payload = json.loads(http.calls[0][1].decode('utf-8'))

        self.assertEqual('hello', payload[0]['message'])
        self.assertEqual('info', payload[0]['level'])
        self.assertEqual('7', payload[0]['camera_id'])
        self.assertEqual('whatever:x', payload[0]['misc'])

    def test_targets_do_not_share_fields(self):
        loggly_http = FakeHttp(status=200)
        better_stack_http = FakeHttp(status=202)

        _loggerCore.set_loggly(
            'tok', 'app-prod', http=loggly_http,
            max_batch_size=1, flush_interval=0.05)
        _loggerCore.set_better_stack(
            'src', 'host.example.com', http=better_stack_http,
            max_batch_size=1, flush_interval=0.05)

        _loggerCore.info('hello')

        self.assertTrue(loggly_http.wait_for_calls(1))
        self.assertTrue(better_stack_http.wait_for_calls(1))

        loggly_record = json.loads(loggly_http.calls[0][1].decode('utf-8'))
        self.assertNotIn('dt', loggly_record)
