import asyncio
import aiohttp

from .executor import PermanentFailure

TOO_MANY_REQUESTS = 429


class HttpTransport:
    """Sends requests to a URL using a persistent aiohttp session."""

    def __init__(self, url, headers, timeout):
        self.__url = url
        self.__headers = headers
        self.__timeout = timeout
        self.__session = aiohttp.ClientSession()

    async def __call__(self, body):
        await asyncio.wait_for(self.__post(body), self.__timeout)

    async def __post(self, body):
        async with self.__session.post(self.__url, data=body,
                                       headers=self.__headers) as response:
            detail = await response.read()

            if 200 <= response.status < 300:
                return

            message = ('the ingest endpoint returned HTTP %d: %s'
                       % (response.status, detail[:200]))

            if 400 <= response.status < 500 and response.status != TOO_MANY_REQUESTS:
                raise PermanentFailure(message)

            raise IOError(message)

    async def close(self):
        await self.__session.close()
