import aiohttp
import asyncio
import json
import threading
import time

from aiohttp import web

from ..sinks.executor import PermanentFailure, RetryableFailure

ALWAYS = 10 ** 6
MAX_BODY_SIZE = 64 * 1024 * 1024


async def eventually(predicate, timeout=2.0, message='condition never held'):
    deadline = asyncio.get_running_loop().time() + timeout

    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f'{message} after {timeout}s')
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
            raise AssertionError(f'{message} after {timeout}s')
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
        self.__peers = set()

        self.__loop = asyncio.new_event_loop()
        self.__thread = threading.Thread(target=self.__loop.run_forever,
                                         daemon=True)
        self.__thread.start()

        self.__runner = web.AppRunner(self.__app(), access_log=None)
        self.__call(self.__start())

    def __call(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.__loop).result()

    def __app(self):
        app = web.Application(client_max_size=MAX_BODY_SIZE)
        app.router.add_post('/{path:.*}', self.__handle)
        return app

    async def __start(self):
        await self.__runner.setup()
        await web.TCPSite(self.__runner, '127.0.0.1', 0).start()

    async def __handle(self, request):
        self.__peers.add(request.transport.get_extra_info('peername'))
        headers = {k.lower(): v for k, v in request.headers.items()}
        self.requests.append((request.path_qs, headers, await request.read()))

        await asyncio.sleep(self.delay)

        response = web.StreamResponse(status=self.status)
        response.content_length = len(self.body)

        try:
            await response.prepare(request)
            await asyncio.sleep(self.body_delay)
            await response.write(self.body)
            await response.write_eof()
        except ConnectionResetError:
            pass

        return response

    @property
    def connections(self):
        return len(self.__peers)

    @property
    def url(self):
        host, port = self.__runner.addresses[0][:2]
        return f'http://{host}:{port}/'

    def close(self):
        self.__call(self.__runner.cleanup())
        self.__loop.call_soon_threadsafe(self.__loop.stop)
        self.__thread.join()
        self.__loop.close()


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
