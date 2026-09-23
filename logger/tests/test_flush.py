import contextlib
import io
import unittest

from unittest import mock

from ..sinks import loggly
from .support import FakeIngestServer


class FlushTest(unittest.TestCase):

    def test_timeout(self):
        server = FakeIngestServer(status=200, delay=5.0)
        self.addCleanup(server.close)

        with mock.patch.object(loggly, 'BULK_URL', server.url + '{}/{}'):
            session = loggly.LogglySession('the-token', 'the-tag')
            session.send({'message': 'stuck'})

            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                flushed = session.flush(timeout=0.2)

        self.assertFalse(flushed)
        self.assertIn('flush', stderr.getvalue())
