import json
import os
import subprocess
import sys
import textwrap
import unittest

from .support import FakeIngestServer

CHILD = textwrap.dedent("""
    from logger.sinks import loggly

    loggly.BULK_URL = __import__('os').environ['INGEST_URL']

    session = loggly.LogglySession('the-token', 'the-tag')
    for i in range(100):
        session.send({'message': 'message-%d' % i})

    # exits without flushing on purpose
""")


class ProcessExitTest(unittest.TestCase):

    def test_flushes_on_exit(self):
        server = FakeIngestServer(status=200)
        self.addCleanup(server.close)

        environment = dict(os.environ, INGEST_URL=server.url + '{}/{}',
                           PYTHONPATH=os.getcwd())
        finished = subprocess.run([sys.executable, '-c', CHILD],
                                  cwd=os.getcwd(), env=environment,
                                  capture_output=True, timeout=30)

        self.assertEqual(finished.returncode, 0, finished.stderr.decode())

        delivered = [json.loads(line)['message']
                     for _, _, body in server.requests
                     for line in body.split(b'\n')]
        self.assertEqual(len(delivered), 100,
                         'records queued at exit were lost')
