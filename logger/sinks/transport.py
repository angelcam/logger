import asyncio
import aiohttp


class HttpTransport:
    """Sends requests to a URL using a persistent aiohttp session."""

    def __init__(self, url, headers, timeout):
        self.__url = url
        self.__headers = headers
        self.__timeout = timeout
        self.__session = aiohttp.ClientSession()

    async def __call__(self, body):
        response = await asyncio.wait_for(
            self.__session.post(self.__url, data=body, headers=self.__headers),
            self.__timeout)

        try:
            if not 200 <= response.status < 300:
                raise IOError('the ingest endpoint returned HTTP %d'
                              % response.status)
        finally:
            await response.release()

    async def close(self):
        await self.__session.close()
