"""This module contains the code to get Camera, NVR and streaming data from a SecuritySpy NVR."""
from __future__ import annotations

import abc
import datetime
import json
import logging
import xmltodict

from typing import Any
from base64 import b64encode

import aiohttp
import asyncio

from .const import (
    CAMERA_MESSAGES,
    DEFAULT_SNAPSHOT_HEIGHT,
    DEFAULT_SNAPSHOT_WIDTH,
    DEVICE_UPDATE_INTERVAL_SECONDS,
    EVENT_MESSAGES,
    RECORDING_TYPE_ACTION,
    RECORDING_TYPE_CONTINUOUS,
    RECORDING_TYPE_MOTION,
    SERVER_ID,
    SERVER_NAME,
    WEBSOCKET_CHECK_INTERVAL_SECONDS,
)

from .data import (
    SecSpyServerData,
)

_LOGGER = logging.getLogger(__name__)

class SecuritySpyError(Exception):
    """Define a base error."""

class InvalidCredentials(SecuritySpyError):
    """Define an error related to invalid or missing Credentials."""

class RequestError(SecuritySpyError):
    """Define an error related to invalid requests."""

class ResultError(SecuritySpyError):
    """Define an error related to the result returned from a request."""

class SecuritySpyAPIBase:
    """Baseclass to use as dependency injection pattern for easier automatic testing."""

    @abc.abstractmethod
    async def async_api_request( self, url: str) -> dict[str, Any]:
        """Override this."""
        raise NotImplementedError(
            "users must define async_api_request to use this base class"
        )

class SecuritySpyAPI(SecuritySpyAPIBase):
    """Default implementation for SecuritySpy api."""

    def __init__(self) -> None:
        """Init the API with or without session."""
        self.session = None

    async def async_api_request(self, url: str, process_json: bool = True) -> dict[str, Any]:
        """Get data from SecuritySpy API."""

        _LOGGER.debug("URL CALLED: %s", url)

        is_new_session = False
        if self.session is None:
            self.session = aiohttp.ClientSession()
            is_new_session = True

        async with self.session.get(url) as response:
            if response.status != 200:
                if is_new_session:
                    await self.session.close()
                raise RequestError(
                    f"Requesting data failed: {response.status} - Reason: {response.reason}"
                )
            if process_json:
                data = await response.text()
                if is_new_session:
                    await self.session.close()

                json_raw = xmltodict.parse(data)
                json_response = json.loads(json.dumps(json_raw))

                return json_response

            raw_data = await response.read()
            return raw_data

class SecuritySpy:
    """Class that uses the SecuritySpy HTTP Webserver to retrieve data."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        session: aiohttp.ClientSession = None,
        min_classify_score: int = 50,
        use_ssl: bool = False,
        api: SecuritySpyAPIBase = SecuritySpyAPI(),
    ) -> None:
        """Return data from SecuritySpy."""
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._api = api
        self._min_score = min_classify_score
        self._use_ssl = use_ssl
        self._xmldata = None
        self._base_url = f"https://{self._host}:{self._port}" if self._use_ssl else f"http://{self._host}:{self._port}"
        self._token = b64encode(bytes(f"{self._username}:{self._password}", "utf-8")).decode()
        self._ws_subscriptions = []
        self._ws_stream = None
        self._ws_task:asyncio.Task | None = None
        self._ws_session = None

        if session:
            self._api.session = session


    @property
    def is_listening(self) -> bool:
        """Return if the client is listening for messages."""
        return self._ws_task is not None

#########################################
# EVENT STREAM FUNCTIONS
#########################################

    async def start_listening(self) -> None:
        """Connect the Webserver and start listening for messages."""
        if self._ws_task is not None:
            return

        event_url = f"{self._base_url}/eventStream?version=3&format=multipart&auth={self._token}"
        timeout = aiohttp.ClientTimeout()
        if not self._ws_session:
            self._ws_session = aiohttp.ClientSession(timeout=timeout)

        try:
            self._ws_stream = await self._ws_session.request("get", url=event_url)
        except aiohttp.client.ClientConnectionError:
            return
        except Exception as uerr:
            _LOGGER.debug("STREAM: Unhandled error: %s", uerr)
            return

        self._ws_task = asyncio.ensure_future(self._start_event_streamer())

    async def stop_listening(self) -> None:
        """Disconnect the webserver."""
        if self._ws_task is None:
            return

        if self._ws_session is not None and not self._ws_session.closed:
            await self._ws_session.close()

        self._ws_task.cancel()
        try:
            await self._ws_task
        except asyncio.CancelledError:
            pass
        finally:
            self._ws_task = None
            _LOGGER("STREAM: Stopped listening")

    async def _start_event_streamer(self) -> None:
        """Start the Webserver stream listener"""
        assert self._ws_session
        while not self._ws_session.closed:
            async for msg in self._ws_stream.content:
                data = msg.decode("UTF-8").strip()
                self._process_message(data)

    def _process_message(self, data: str) -> None:
        try:
            if data[:14].isnumeric():
                _LOGGER.debug(data)
        except Exception as err:
            _LOGGER.exception("STREAM: Error processing stream. Error: %s", err)
            return

        return


    def subscribe_websocket(self, ws_callback):
        """Subscribe to websocket events.
        Return a callback that will unsubscribe.
        """

        def _unsub_ws_callback():
            self._ws_subscriptions.remove(ws_callback)

        _LOGGER.debug("Adding subscription: %s", ws_callback)
        self._ws_subscriptions.append(ws_callback)
        return _unsub_ws_callback

#########################################
# INFORMATION FUNCTIONS
#########################################

    async def get_server_information(self) -> list[SecSpyServerData]:
        """Return list of Server data."""
        api_url =  f"{self._base_url}/systemInfo?auth={self._token}"
        xml_data = await self._api.async_api_request(api_url)

        return _get_server_information(xml_data)

#########################################
# HOME ASSISTANT SERVICES
#########################################

    async def get_snapshot_image(self, camera_id: str, width: int | None = None, height: int | None = None) -> bytes:
        """Return Snapshot image from the specified Camera."""
        image_width = width or DEFAULT_SNAPSHOT_WIDTH
        image_height = height or DEFAULT_SNAPSHOT_HEIGHT

        api_url = f"{self._base_url}/image?cameraNum={camera_id}&width={image_width}&height={image_height}&quality=75&auth={self._token}"
        return await self._api.async_api_request(api_url, False)

    async def get_latest_motion_recording(self, camera_id: str) -> bytes:
        """Return the latest motion recording file."""

        # Get the latest file name
        file_url = f"{self._base_url}/download?cameraNum={camera_id}&mcFilesCheck=1&ageText=1&results=1&format=xml&auth={self._token}"
        json_data = await self._api.async_api_request(file_url)
        download_url = json_data["feed"]["entry"]["link"]["@href"]

        # Retrieve the file
        api_url = f"{self._base_url}/{download_url}?auth={self._token}"
        return await self._api.async_api_request(api_url, False)

#########################################
# DATA PROCESSING
#########################################

def _get_server_information(api_result) -> list[SecSpyServerData]:
    """Return formatted server data from API."""

    nvr = api_result["system"]["server"]
    sys_info = api_result["system"]
    sched_preset = sys_info.get("schedulepresetlist")
    presets = []
    if sched_preset is not None:
        for preset in sched_preset["schedulepreset"]:
            presets.append(preset)

    server_data = SecSpyServerData(
        ip_address=nvr["ip1"],
        name=nvr["server-name"],
        port=8000,
        presets=presets,
        uuid=nvr["uuid"],
        version=nvr["version"],
    )

    return server_data
