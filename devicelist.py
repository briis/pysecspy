from pysecspy.secspy_server import SecSpyServer
from aiohttp import ClientSession
import asyncio
import logging
import json


_LOGGER = logging.getLogger(__name__)

USERNAME = "YOUR_USERNAME"
PASSWORD = "YOUR_PASSWORD"
IPADDRESS = "YOUR_IP_ADDRESS"
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

    # image = await secspy.get_snapshot_image("0")
    
    data = await secspy.update(True)
    print(json.dumps(data, indent=1))

    # await secspy.set_camera_recording("1", "on_motion")

    # Close the Session
    await session.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(devicedata())
loop.close()