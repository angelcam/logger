import asyncio
import aiohttp

from .executor import PermanentFailure, RetryableFailure

TOO_MANY_REQUESTS = 429


class HttpTransport:
    """Sends requests to a URL using a persistent aiohttp session."""

    def __init__(self, url, headers, timeout):
        self.__url = url
        self.__headers = headers
        self.__timeout = timeout
        self.__session = aiohttp.ClientSession()

    async def __call__(self, body):
        try:
            await asyncio.wait_for(self.__post(body), self.__timeout)
        except aiohttp.ClientConnectorError as ex:
            raise RetryableFailure(
                f'could not reach the ingest endpoint: {ex}')

    async def __post(self, body):
        async with self.__session.post(self.__url, data=body,
                                       headers=self.__headers) as response:
            detail = await response.read()

            if 200 <= response.status < 300:
                return

            message = (f'the ingest endpoint returned HTTP {response.status}: '
                       f'{detail[:200]}')

            if response.status == TOO_MANY_REQUESTS or response.status >= 500:
                raise RetryableFailure(message)

            if 400 <= response.status < 500:
                raise PermanentFailure(message)

            raise IOError(message)

    async def close(self):
        await self.__session.close()
