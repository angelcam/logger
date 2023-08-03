import asyncio
import aiohttp
import traceback

from asyncio import Semaphore
from collections import deque
from threading import Thread


class AsyncQueue:

    def __init__(self):
        self.queue = deque()
        self.available = Semaphore(0)

    def __len__(self):
        return len(self.queue)

    def __bool__(self):
        return bool(self.queue)

    def __getitem__(self, idx):
        return self.queue[idx]

    def push_back(self, item):
        self.queue.append(item)
        self.available.release()

    async def pop_front(self):
        await self.available.acquire()
        return self.queue.popleft()


class LogglyExecutor(Thread):
    """
    The executor runs the internal event loop in a separate daemon thread and allows its users to send log messages
    asynchronously.
    """

    def __init__(self, token, tag, timeout, max_tasks=4):
        super().__init__(daemon=True)

        self.__url = 'https://logs-01.loggly.com/bulk/{}/tag/{}/'.format(token, tag)
        self.__event_loop = asyncio.new_event_loop()
        self.__session = aiohttp.ClientSession(loop=self.__event_loop)
        self.__timeout = timeout
        self.__queue = AsyncQueue()
        self.__tasks = Semaphore(max_tasks)

    def run(self):
        self.__event_loop.create_task(self.__runner())
        self.__event_loop.run_forever()

    def send(self, event):
        def push():
            self.__queue.push_back(event.encode('utf-8'))

        self.__event_loop.call_soon_threadsafe(push)

    async def __runner(self):
        while True:
            batch = await self.__queue.pop_front()
            while self.__queue:
                batch_len = len(batch)
                next_len = len(self.__queue[0])
                if (batch_len + next_len + 1) >= 4000000:
                    break
                batch += b'\n' + (await self.__queue.pop_front())
            await self.__tasks.acquire()
            task = self.__event_loop.create_task(self.__send_batch(batch))
            task.add_done_callback(lambda t: self.__tasks.release())

    async def __send_batch(self, data):
        try:
            headers = {
                'content-type': 'text/plain',
            }
            response = await asyncio.wait_for(
                self.__session.post(self.__url, data=data, headers=headers),
                self.__timeout)
            await response.release()
        except Exception:
            traceback.print_exc()


class LogglySession(object):
    """
    LogglySession for Python 3.x
    """

    def __init__(self, token, tag, timeout=20.0):
        self.__executor = LogglyExecutor(token, tag, timeout)
        self.__executor.start()

    def send(self, data):
        self.__executor.send(data)
