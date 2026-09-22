import asyncio
import http.server
import threading
import time


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
    def __init__(self, failures=1):
        super().__init__()
        self.remaining_failures = failures
        self.attempts = 0

    async def __call__(self, body):
        self.attempts += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise IOError('transport is down')
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

    def __init__(self, status=202, delay=0.0):
        self.status = status
        self.delay = delay
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
                self.send_header('content-length', '0')
                self.end_headers()

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
