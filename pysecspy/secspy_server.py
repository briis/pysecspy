"""Module to communicate with the SecuritySpy API."""
import logging
import asyncio
import sys
import datetime
import time
import xmltodict

from typing import Optional
import aiohttp
from aiohttp import client_exceptions
from base64 import b64encode

from pysecspy.const import (
    DEVICE_UPDATE_INTERVAL_SECONDS,
    WEBSOCKET_CHECK_INTERVAL_SECONDS,
)

from pysecspy.secspy_data import (
    process_camera,
    PROCESSED_EVENT_EMPTY,
    SecspyDeviceStateMachine,
)

from pysecspy.errors import (
    InvalidCredentials,
    RequestError,
    ResultError,
)

_LOGGER = logging.getLogger(__name__)

class SecSpyServer:
    """Updates device states and attributes."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, username: str, password: str):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._base_url = f"http://{host}:{port}"
        self._token = b64encode(bytes(f"{self._username}:{self._password}", "utf-8")).decode()
        self.headers = {"Content-Type": "text/xml"}
        self._is_authenticated = False
        self._last_device_update_time = 0
        self._last_websocket_check = 0
        self._device_state_machine = SecspyDeviceStateMachine()

        self._processed_data = {}

        self.req = session
        self.headers = None
        self.ws_session = None
        self.ws_connection = None
        self.ws_task = None
        self._ws_subscriptions = []
        self._is_first_update = True

    @property
    def devices(self):
        """ Returns a JSON formatted list of Devices. """
        return self._processed_data

    async def update(self, force_camera_update=False) -> dict:
        """Updates the status of devices."""

        current_time = time.time()
        device_update = False
        if (
            not self.ws_connection
            and force_camera_update
            or (current_time - DEVICE_UPDATE_INTERVAL_SECONDS)
            > self._last_device_update_time
        ):
            _LOGGER.debug("Doing device update")
            device_update = True
            await self._get_device_list(not self.ws_connection)
            self._last_device_update_time = current_time
        else:
            _LOGGER.debug("Skipping device update")

        if (current_time - WEBSOCKET_CHECK_INTERVAL_SECONDS
            > self._last_websocket_check
        ):
            _LOGGER.debug("Checking websocket")
            self._last_websocket_check = current_time
            await self.async_connect_ws()

        # If the websocket is connected/connecting
        # we do not need to get events
        if self.ws_connection or self._last_websocket_check == current_time:
            _LOGGER.debug("Skipping update since websocket is active")
            return self._processed_data if device_update else {}

        self._reset_device_events()
        updates = await self._get_events(lookback=10)

        return self._processed_data if device_update else updates

    async def async_connect_ws(self):
        """Connect the websocket."""
        if self.ws_connection is not None:
            return

        if self.ws_task is not None:
            try:
                self.ws_task.cancel()
                self.ws_connection = None
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Could not cancel ws_task")
        self.ws_task = asyncio.ensure_future(self._setup_websocket())

    async def async_disconnect_ws(self):
        """Disconnect the websocket."""
        if self.ws_connection is None:
            return

        await self.ws_connection.close()
        await self.ws_session.close()

    async def _get_device_list(self, include_events) -> None:
        """Get a list of devices connected to the NVR."""

        system_uri = f"{self._base_url}/systemInfo?auth={self._token}"
        response = await self.req.get(
            system_uri,
            headers=self.headers,
        )
        if response.status != 200:
            raise RequestError(
                f"Fetching Camera List failed: {response.status} - Reason: {response.reason}"
            )
        data = await response.read()
        json_response = xmltodict.parse(data)
        server_id = json_response["system"]["server"]["uuid"]
        # if not self.ws_connection and "lastUpdateId" in json_response:
        #     self.last_update_id = json_response["lastUpdateId"]

        self._process_cameras_json(json_response, server_id, include_events)

        self._is_first_update = False


    def _process_cameras_json(self, json_response, server_id, include_events):
        for camera in json_response["system"]["cameralist"]["camera"]:
            camera_id = camera["number"]
            if self._is_first_update:
                self._update_device(camera_id, PROCESSED_EVENT_EMPTY)
            self._device_state_machine.update(camera_id, camera)
            self._update_device(
                camera_id,
                process_camera(
                    server_id,
                    self._host,
                    camera,
                    include_events or self._is_first_update,
                ),
            )

    def _update_device(self, device_id, processed_update):
        """Update internal state of a device."""
        self._processed_data.setdefault(device_id, {}).update(processed_update)

    async def _get_events(
        self, lookback: int = 86400, camera=None, start_time=None, end_time=None
    ) -> None:
        """Load the Event Log and loop through items to find motion events."""

        event_uri = f"{self._base_url}/eventStream?version=3&format=multipart&auth={self._token}"

        response = await self.req.get(
            event_uri,
            headers=self.headers,
        )
        if response.status != 200:
            raise RequestError(
                f"Fetching Eventlog failed: {response.status} - Reason: {response.reason}"
            )

        updated = {}
        for event in await xmltodict.parse(response.read()):
            _LOGGER.debug("EVENT STRING: %s", event)
            # if event["type"] not in (EVENT_MOTION, EVENT_RING, EVENT_SMART_DETECT_ZONE):
            #     continue

            # camera_id = event["camera"]
            # self._update_device(
            #     camera_id,
            #     process_event(event, self._minimum_score, event_ring_check_converted),
            # )
            # updated[camera_id] = self._processed_data[camera_id]

        return updated


    def _reset_device_events(self) -> None:
        """Reset device events between device updates."""
        for device_id in self._processed_data:
            self._update_device(device_id, PROCESSED_EVENT_EMPTY)


    async def _setup_websocket(self):
        """Setup the Event Websocket."""
        ip_address = self._base_url.split("://")
        url = f"{self._base_url}/eventStream?version=3&format=multipart&auth={self._token}"
        # if self.last_update_id:
        #     url += f"?lastUpdateId={self.last_update_id}"
        if not self.ws_session:
            self.ws_session = aiohttp.ClientSession()
        _LOGGER.debug("WS connecting to: %s", url)

        self.ws_connection = await self.ws_session.ws_connect(url, headers=self.headers
        )
        try:
            async for msg in self.ws_connection:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    try:
                        self._process_ws_message(msg)
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.exception("Error processing websocket message")
                        return
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        finally:
            _LOGGER.debug("websocket disconnected")
            self.ws_connection = None

    def subscribe_websocket(self, ws_callback):
        """Subscribe to websocket events.

        Returns a callback that will unsubscribe.
        """

        def _unsub_ws_callback():
            self._ws_subscriptions.remove(ws_callback)

        _LOGGER.debug("Adding subscription: %s", ws_callback)
        self._ws_subscriptions.append(ws_callback)
        return _unsub_ws_callback
