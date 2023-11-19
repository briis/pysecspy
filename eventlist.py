from __future__ import annotations

from dotenv import load_dotenv
import os
"""Test program for the event functions."""

from pysecspy.secspy_server import SecSpyServer
from aiohttp import ClientSession
import asyncio
import logging


_LOGGER = logging.getLogger(__name__)

load_dotenv()
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
ipaddress = os.getenv("IPADDRESS")
port = os.getenv("PORT")

async def devicedata():

    logging.basicConfig(level=logging.DEBUG)

    session = ClientSession()

    # Log in to SecuritySpy
    secspy = SecSpyServer(
        session,
        ipaddress,
        port,
        username,
        password,
    )

    await secspy.update()
    unsub = secspy.subscribe_websocket(subscriber)

    for i in range(150000):
        await asyncio.sleep(1)

    # Close the Session
    await session.close()
    await secspy.async_disconnect_ws()
    unsub()


def subscriber(updated):
    _LOGGER.info("Subscription: updated=%s", updated)


loop = asyncio.get_event_loop()
loop.run_until_complete(devicedata())
loop.close()