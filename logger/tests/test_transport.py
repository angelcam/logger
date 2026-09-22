import asyncio
import unittest

from ..sinks.executor import PermanentFailure
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

        with self.assertRaises(PermanentFailure) as caught:
            await transport(b'too big')

        self.assertIn('413', str(caught.exception))

    async def test_connection_reuse(self):
        server = self._server(status=202, body_delay=0.05)
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

    async def test_permanent_on_client_error(self):
        server = self._server(status=403)
        transport = await self._transport(server)

        with self.assertRaises(PermanentFailure):
            await transport(b'{"m":"a"}')

    async def test_retryable_on_server_error(self):
        server = self._server(status=503)
        transport = await self._transport(server)

        with self.assertRaises(Exception) as caught:
            await transport(b'{"m":"a"}')

        self.assertNotIsInstance(caught.exception, PermanentFailure)

    async def test_retryable_on_rate_limit(self):
        server = self._server(status=429)
        transport = await self._transport(server)

        with self.assertRaises(Exception) as caught:
            await transport(b'{"m":"a"}')

        self.assertNotIsInstance(caught.exception, PermanentFailure)

    async def test_error_includes_the_body(self):
        server = self._server(status=400, body=b'tag is not valid')
        transport = await self._transport(server)

        with self.assertRaises(PermanentFailure) as caught:
            await transport(b'{"m":"a"}')

        self.assertIn('tag is not valid', str(caught.exception))

    async def test_timeout_covers_the_body(self):
        server = self._server(status=202, body_delay=1.0)
        transport = await self._transport(server, timeout=0.2)

        with self.assertRaises(asyncio.TimeoutError):
            await transport(b'{"m":"a"}')
