import aiohttp
import asyncio
import http.server
import json
import threading
import time

from ..sinks.executor import PermanentFailure, RetryableFailure

ALWAYS = 10 ** 6


async def eventually(predicate, timeout=2.0, message='condition never held'):
    deadline = asyncio.get_running_loop().time() + timeout

    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError('%s after %ss' % (message, timeout))
        await asyncio.sleep(0.005)


class RecordingPost:
    def __init__(self):
        self.bodies = []

    async def __call__(self, body):
        self.bodies.append(body)

    @property
    def records(self):
        return [line for body in self.bodies for line in body.split(b'\n')]


class BlockingPost:
    """A transport that never finishes, to observe how many sends are in flight."""

    def __init__(self):
        self.in_flight = 0
        self.released = asyncio.Event()

    async def __call__(self, body):
        self.in_flight += 1
        await self.released.wait()


class SlowPost(RecordingPost):
    def __init__(self, delay=0.02):
        super().__init__()
        self.delay = delay

    async def __call__(self, body):
        await asyncio.sleep(self.delay)
        await super().__call__(body)


class FailingPost(RecordingPost):
    error = RetryableFailure
    message = 'transport is down'

    def __init__(self, failures=1):
        super().__init__()
        self.remaining_failures = failures
        self.attempts = 0

    async def __call__(self, body):
        self.attempts += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise self.error(self.message)
        await super().__call__(body)


def wait_until(predicate, timeout=5.0, message='condition never held'):
    """Blocking counterpart of eventually(), for code that owns its own loop."""
    deadline = time.monotonic() + timeout

    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError('%s after %ss' % (message, timeout))
        time.sleep(0.005)


class FakeIngestServer:
    """A real HTTP/1.1 server for testing transport and connection reuse."""

    def __init__(self, status=202, delay=0.0, body=b'{"response":"ok"}',
                 body_delay=0.0):
        self.status = status
        self.delay = delay
        self.body = body
        self.body_delay = body_delay
        self.requests = []
        self.connections = 0

        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def setup(self):
                server.connections += 1
                super().setup()

            def do_POST(self):
                length = int(self.headers.get('content-length', 0))
                body = self.rfile.read(length)
                server.requests.append((self.path, dict(self.headers), body))

                if server.delay:
                    time.sleep(server.delay)

                self.send_response(server.status)
                self.send_header('content-length', str(len(server.body)))
                self.end_headers()

                if server.body_delay:
                    self.wfile.flush()
                    time.sleep(server.body_delay)

                self.wfile.write(server.body)

            def log_message(self, *args):
                pass

        self.__httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.__thread = threading.Thread(target=self.__httpd.serve_forever,
                                         daemon=True)
        self.__thread.start()

    @property
    def url(self):
        host, port = self.__httpd.server_address[:2]
        return 'http://%s:%d/' % (host, port)

    def close(self):
        self.__httpd.shutdown()
        self.__httpd.server_close()


class TruncatedPost(FailingPost):
    error = aiohttp.ClientPayloadError
    message = 'the response was cut short'

    def __init__(self, failures=ALWAYS):
        super().__init__(failures)


class RejectingPost(FailingPost):
    """A transport whose failure retrying cannot fix, e.g. a rejected token."""

    error = PermanentFailure
    message = 'the token was rejected'

    def __init__(self, failures=ALWAYS):
        super().__init__(failures)


class TimingOutPost(FailingPost):
    error = asyncio.TimeoutError
    message = 'no response in time'

    def __init__(self, failures=ALWAYS):
        super().__init__(failures)


def delivered(server):
    """All records received by the server, across all requests."""
    return [json.loads(line)['message']
            for _, _, body in server.requests
            for line in body.split(b'\n')]
