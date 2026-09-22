import asyncio
import unittest

from ..sinks.transport import HttpTransport
from .support import FakeIngestServer


class HttpTransportTest(unittest.IsolatedAsyncioTestCase):

    def _server(self, **options):
        server = FakeIngestServer(**options)
        self.addCleanup(server.close)
        return server

    async def _transport(self, server, timeout=5.0, headers=None):
        transport = HttpTransport(server.url, headers or {'content-type': 'x'},
                                  timeout)
        self.addAsyncCleanup(transport.close)
        return transport

    async def test_posts_body(self):
        server = self._server(status=202)
        transport = await self._transport(
            server, headers={'authorization': 'Bearer secret',
                             'content-type': 'application/x-ndjson'})

        await transport(b'{"m":"a"}\n{"m":"b"}')

        path, headers, body = server.requests[0]
        self.assertEqual(body, b'{"m":"a"}\n{"m":"b"}')
        self.assertEqual(headers['authorization'], 'Bearer secret')
        self.assertEqual(headers['content-type'], 'application/x-ndjson')

    async def test_bad_status(self):
        server = self._server(status=413)
        transport = await self._transport(server)

        with self.assertRaises(IOError) as caught:
            await transport(b'too big')

        self.assertIn('413', str(caught.exception))

    async def test_connection_reuse(self):
        server = self._server(status=202)
        transport = await self._transport(server)

        for _ in range(5):
            await transport(b'{"m":"a"}')

        self.assertEqual(len(server.requests), 5)
        self.assertEqual(server.connections, 1, 'opened a connection per request')

    async def test_timeout(self):
        server = self._server(status=202, delay=0.5)
        transport = await self._transport(server, timeout=0.1)

        with self.assertRaises(asyncio.TimeoutError):
            await transport(b'{"m":"a"}')
