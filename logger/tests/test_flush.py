import contextlib
import io
import unittest

from unittest import mock

from ..sinks import loggly
from .support import FakeIngestServer, delivered


class FlushTest(unittest.TestCase):

    def _session(self, **server_options):
        server = FakeIngestServer(status=200, **server_options)
        self.addCleanup(server.close)

        patched = mock.patch.object(loggly, 'BULK_URL', server.url + '{}/{}')
        patched.start()
        self.addCleanup(patched.stop)

        return server, loggly.LogglySession('the-token', 'the-tag')

    def test_waits_for_queue(self):
        server, session = self._session(delay=0.05)
        expected = [f'message-{i}' for i in range(200)]

        for message in expected:
            session.send({'message': message})

        self.assertTrue(session.flush(timeout=10), 'flush reported a timeout')

        self.assertEqual(sorted(delivered(server)), sorted(expected))

    def test_timeout(self):
        server, session = self._session(delay=5.0)
        session.send({'message': 'stuck'})

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            flushed = session.flush(timeout=0.2)

        self.assertFalse(flushed)
        self.assertIn('flush', stderr.getvalue())
