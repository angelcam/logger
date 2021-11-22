import asyncio
import aiohttp
import traceback

from threading import Thread


class LogglyExecutor(Thread):
    """
    The executor runs the internal event loop in a separate daemon thread and allows its users to send log messages
    asynchronously.
    """

    def __init__(self, token, tag, timeout):
        super().__init__(daemon=True)

        self.__url = 'https://logs-01.loggly.com/inputs/{}/tag/{}'.format(token, tag)
        self.__event_loop = asyncio.new_event_loop()
        self.__session = aiohttp.ClientSession(loop=self.__event_loop)
        self.__timeout = timeout

    def run(self):
        self.__event_loop.run_forever()

    def send(self, data):
        asyncio.run_coroutine_threadsafe(
            self.__async_send(data),
            self.__event_loop)

    async def __async_send(self, data):
        try:
            response = await asyncio.wait_for(
                self.__session.post(self.__url, data=data),
                self.__timeout,
                loop=self.__event_loop)
            await response.release()
        except Exception as ex:
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
