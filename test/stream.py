"""Test program."""
from __future__ import annotations

import aiofiles
from httpx import AsyncClient
import asyncio
import logging
import json
import time


_LOGGER = logging.getLogger(__name__)

async def main() -> None:
    """Async test module."""

    logging.basicConfig(level=logging.DEBUG)
    start = time.time()

    async with AsyncClient() as http_client:
        url = "http://192.168.1.67:8000/eventStream?version=3&format=multipart&auth=YWRtaW46c2tpdEh0N0tMc2Z5"

        async with aiofiles.open("file.txt", mode='wb') as tmp_file:
            async with http_client.stream('GET', url) as response:
                response.raise_for_status()
                response.read()
                async for msg in response.content:
                    data = msg.decode("UTF-8").strip()
                    await tmp_file.write(data)

    end = time.time()

    _LOGGER.info("Execution time: %s seconds", end - start)

asyncio.run(main())
