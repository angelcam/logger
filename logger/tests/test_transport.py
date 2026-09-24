import asyncio
import contextlib
import unittest

from ..sinks.executor import PermanentFailure, RetryableFailure
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

        _, headers, body = server.requests[0]
        self.assertEqual(body, b'{"m":"a"}\n{"m":"b"}')
        self.assertEqual(headers['authorization'], 'Bearer secret')
        self.assertEqual(headers['content-type'], 'application/x-ndjson')

    async def test_client_error(self):
        server = self._server(status=400, body=b'tag is not valid')
        transport = await self._transport(server)

        with self.assertRaises(PermanentFailure) as caught:
            await transport(b'{"m":"a"}')

        self.assertIn('400', str(caught.exception))
        self.assertIn('tag is not valid', str(caught.exception))

    async def test_retryable_status(self):
        for status in (429, 503):
            with self.subTest(status=status):
                transport = await self._transport(self._server(status=status))

                with self.assertRaises(RetryableFailure):
                    await transport(b'{"m":"a"}')

    async def test_cannot_connect(self):
        transport = HttpTransport('http://127.0.0.1:1/', {}, 5.0)
        self.addAsyncCleanup(transport.close)

        with self.assertRaises(RetryableFailure):
            await transport(b'{"m":"a"}')

    async def test_connection_reuse(self):
        for status in (202, 503):
            with self.subTest(status=status):
                server = self._server(status=status, body_delay=0.05)
                transport = await self._transport(server)

                for _ in range(5):
                    with contextlib.suppress(RetryableFailure):
                        await transport(b'{"m":"a"}')

                self.assertEqual(len(server.requests), 5)
                self.assertEqual(server.connections, 1,
                                 'opened a connection per request')

    async def test_timeout(self):
        for options in ({'delay': 0.5}, {'body_delay': 0.5}):
            with self.subTest(**options):
                server = self._server(status=202, **options)
                transport = await self._transport(server, timeout=0.1)

                with self.assertRaises(asyncio.TimeoutError):
                    await transport(b'{"m":"a"}')
