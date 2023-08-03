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


class LogglyExecutor:

    def __init__(self, token, tag, timeout, max_tasks):
        self.__event_loop = asyncio.get_running_loop()
        self.__url = 'https://logs-01.loggly.com/bulk/{}/tag/{}/'.format(token, tag)
        self.__session = aiohttp.ClientSession()
        self.__timeout = timeout
        self.__queue = AsyncQueue()
        self.__tasks = Semaphore(max_tasks)

    def send(self, event):
        def push():
            self.__queue.push_back(event.encode('utf-8'))

        self.__event_loop.call_soon_threadsafe(push)

    async def run(self):
        while True:
            batch = await self.__queue.pop_front()
            while self.__queue:
                batch_len = len(batch)
                next_len = len(self.__queue[0])
                if (batch_len + next_len + 1) >= 4000000:
                    break
                batch += b'\n' + (await self.__queue.pop_front())
            await self.__tasks.acquire()
            task = asyncio.create_task(self.__send_batch(batch))
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


class LogglyThread(Thread):

    def __init__(self, token, tag, timeout, max_tasks=4):
        super().__init__(daemon=True)

        self.token = token
        self.tag = tag
        self.timeout = timeout
        self.max_tasks = max_tasks
        self.executor = None

    def send(self, event):
        if self.executor:
            self.executor.send(event)

    def run(self):
        async def task():
            self.executor = LogglyExecutor(
                self.token,
                self.tag,
                self.timeout,
                self.max_tasks,
            )
            await self.executor.run()

        loop = asyncio.new_event_loop()
        loop.create_task(task())
        loop.run_forever()


class LogglySession(object):
    """
    LogglySession for Python 3.x
    """

    def __init__(self, token, tag, timeout=20.0):
        self.__thread = LogglyThread(token, tag, timeout)
        self.__thread.start()

    def send(self, data):
        self.__thread.send(data)
