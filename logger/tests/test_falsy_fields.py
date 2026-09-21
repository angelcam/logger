import json
import unittest

from ..logger import _loggerCore, INFO
from .support import FakeHttp


class FalsyFieldTest(unittest.TestCase):

    def setUp(self):
        _loggerCore.set_min_level(INFO)
        _loggerCore.set_console(False)
        self.http = FakeHttp(status=202)
        _loggerCore.set_better_stack(
            'src', 'host.example.com', http=self.http,
            max_batch_size=1, flush_interval=0.05)

    def tearDown(self):
        _loggerCore._better_stack.stop()
        _loggerCore._better_stack = None

    def _logged(self, **kwargs):
        _loggerCore.info('m', **kwargs)
        self.assertTrue(self.http.wait_for_calls(1), 'nothing was sent')
        return json.loads(self.http.calls[0][1].decode('utf-8'))[0]

    def test_keeps_zero_std_field(self):
        self.assertEqual('0', self._logged(camera_id=0)['camera_id'])

    def test_keeps_zero_extra_field(self):
        self.assertEqual('retries:0', self._logged(retries=0)['misc'])

    def test_keeps_false_field(self):
        self.assertEqual('recording:False', self._logged(recording=False)['misc'])

    def test_drops_none_field(self):
        self.assertNotIn('camera_id', self._logged(camera_id=None))
