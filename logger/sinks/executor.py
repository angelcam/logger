import asyncio
import concurrent.futures
import sys
import time
import traceback

from asyncio import Semaphore
from collections import deque
from threading import Event, Thread

# how often the executor may complain about drops or failures; a target that
# is down must not bury stderr under one traceback per batch
REPORT_INTERVAL = 10.0
STARTUP_TIMEOUT = 5.0
SEND_ATTEMPTS = 3
RETRY_BACKOFF = 0.5
DRAIN_POLL_INTERVAL = 0.005


class PermanentFailure(Exception):
    """Unrecoverable failure, e.g., rejected token. Skips futile retries."""


def report(message):
    print('logger: %s' % message, file=sys.stderr)


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


async def collect_batch(queue, max_size):
    record = await queue.pop_front()
    batch = [record]
    size = len(record)

    while queue:
        grown = size + 1 + len(queue[0])
        if grown > max_size:
            break
        batch.append(await queue.pop_front())
        size = grown

    return batch


class BatchExecutor:
    """Processes a queue of encoded records into batches for transport.

    Batches are sent immediately without waiting for more records. Concurrency
    is limited by a semaphore, ensuring bursts of logs result in fewer, larger
    requests. Records are only dropped if max_queue_size is set and exceeded.
    """

    def __init__(self, post, max_size, max_tasks=4, max_queue_size=None):
        self.__loop = asyncio.get_running_loop()
        self.__post = post
        self.__max_size = max_size
        self.__max_queue_size = max_queue_size
        self.__queue = AsyncQueue()
        self.__tasks = Semaphore(max_tasks)
        self.__dropped = 0
        self.__lost = 0
        self.__in_flight = 0
        self.__last_drop_report = 0.0
        self.__last_failure_report = 0.0

    @property
    def queue_size(self):
        return len(self.__queue)

    @property
    def dropped(self):
        return self.__dropped

    @property
    def lost(self):
        return self.__lost

    def send(self, record):
        self.__loop.call_soon_threadsafe(self.__push, record)

    def __push(self, record):
        if self.__is_full():
            self.__dropped += 1
            self.__report_drops()
            return

        self.__queue.push_back(record)

    def __report_drops(self):
        now = time.monotonic()
        if now - self.__last_drop_report < REPORT_INTERVAL:
            return

        self.__last_drop_report = now
        report('queue is full, dropped %d records so far' % self.__dropped)

    def __report_failure(self, ex):
        now = time.monotonic()
        if (self.__last_failure_report
                and now - self.__last_failure_report < REPORT_INTERVAL):
            return

        first = not self.__last_failure_report
        self.__last_failure_report = now
        report('failed to deliver %d records so far: %s' % (self.__lost, ex))

        # the traceback is worth one look, not one per batch
        if first:
            traceback.print_exc()

    def __is_full(self):
        return (self.__max_queue_size is not None
                and len(self.__queue) >= self.__max_queue_size)

    async def run(self):
        while True:
            await self.__tasks.acquire()
            batch = await collect_batch(self.__queue, self.__max_size)
            self.__in_flight += 1
            task = asyncio.create_task(self.__send(batch))
            task.add_done_callback(self.__sender_finished)

    def __sender_finished(self, task):
        self.__in_flight -= 1
        self.__tasks.release()

    async def drain(self):
        while self.__queue or self.__in_flight:
            await asyncio.sleep(DRAIN_POLL_INTERVAL)

    async def __send(self, batch):
        body = b'\n'.join(batch)

        for attempt in range(SEND_ATTEMPTS):
            try:
                await self.__post(body)
                return
            except (PermanentFailure, asyncio.TimeoutError) as ex:
                failure = ex
                break
            except Exception as ex:
                failure = ex
                if attempt + 1 < SEND_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF * (2 ** attempt))

        # one bad batch must never stop the executor
        self.__lost += len(batch)
        self.__report_failure(failure)


class SinkThread(Thread):
    """Runs a batch executor in a daemon thread with its own event loop.

    The executor and its asyncio resources are tied to the loop that drives it.
    Callers block briefly for the loop to start, ensuring no log messages are lost.
    """

    def __init__(self, create_executor):
        super().__init__(daemon=True)

        self.__create_executor = create_executor
        self.__executor = None
        self.__loop = None
        self.__ready = Event()
        self.__last_no_loop_report = 0.0

    def send(self, record):
        if not self.__ready.wait(STARTUP_TIMEOUT):
            report('background loop did not start within %ss, dropping a record'
                   % STARTUP_TIMEOUT)
            return

        if self.__executor is None:
            self.__report_no_loop()
            return

        self.__executor.send(record)

    def __report_no_loop(self):
        now = time.monotonic()
        if (self.__last_no_loop_report
                and now - self.__last_no_loop_report < REPORT_INTERVAL):
            return

        self.__last_no_loop_report = now
        report('the background loop is gone, log messages are being dropped')

    def flush(self, timeout):
        if not self.__ready.wait(STARTUP_TIMEOUT) or self.__executor is None:
            return False

        draining = asyncio.run_coroutine_threadsafe(
            self.__executor.drain(), self.__loop)

        try:
            draining.result(timeout)
            return True
        except concurrent.futures.TimeoutError:
            draining.cancel()
            report('flush did not finish within %ss, %d records were not '
                   'delivered' % (timeout, self.__executor.queue_size))
            return False

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.__main())
        except Exception as ex:
            self.__executor = None
            report('the background logging loop stopped: %s' % ex)
            traceback.print_exc()
        finally:
            self.__ready.set()

    async def __main(self):
        self.__loop = asyncio.get_running_loop()
        self.__executor = self.__create_executor()
        self.__ready.set()
        await self.__executor.run()
