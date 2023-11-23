"""Test program to test if the basic information and device data can be retrieved.

Create a .env file add values for USERNAME, PASSWORD, IP_ADDRESS and PORT to the file.
"""
from __future__ import annotations

from dotenv import load_dotenv
import os

from pysecspy import (
    SecuritySpy,
)
import aiohttp
import asyncio
import logging
import time


_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Async test module."""

    logging.basicConfig(level=logging.DEBUG)
    start = time.time()

    load_dotenv()
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    ipaddress = os.getenv("IPADDRESS")
    port = os.getenv("PORT")

    session = aiohttp.ClientSession()
    secspy = SecuritySpy(
        session=session, host=ipaddress, port=port, username=username, password=password
    )

    try:
        await secspy.update()
        cameras = secspy.cameras
        print(cameras)
        await asyncio.sleep(20)
        await secspy.stop_listening()

    except Exception as err:
        print(err)

    end = time.time()

    _LOGGER.info("Execution time: %s seconds", end - start)

    if session is not None:
        await session.close()


asyncio.run(main())
