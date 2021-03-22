from pysecspy.secspy_server import SecSpyServer
from aiohttp import ClientSession
import asyncio
import logging
import json


_LOGGER = logging.getLogger(__name__)

USERNAME = "admin"
PASSWORD = "skitHt7KLsfy"
IPADDRESS = "192.168.1.195"
PORT = 8000

async def devicedata():

    logging.basicConfig(level=logging.DEBUG)

    session = ClientSession()

    # Log in to Unifi Protect
    secspy = SecSpyServer(
        session,
        IPADDRESS,
        PORT,
        USERNAME,
        PASSWORD,
    )

    await secspy.update()
    data = secspy.devices
    print(data)
    json.dumps(data, indent=1)

    # Close the Session
    await session.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(devicedata())
loop.close()