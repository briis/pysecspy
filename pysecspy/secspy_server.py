"""Module to communicate with the SecuritySpy API."""
import asyncio
import logging
import time
from base64 import b64encode

import aiohttp
import xmltodict

from pysecspy.const import (
    CAMERA_MESSAGES,
    DEVICE_UPDATE_INTERVAL_SECONDS,
    EVENT_MESSAGES,
    WEBSOCKET_CHECK_INTERVAL_SECONDS,
)
from pysecspy.errors import RequestError
from pysecspy.secspy_data import (
    PROCESSED_EVENT_EMPTY,
    SecspyDeviceStateMachine,
    SecspyEventStateMachine,
    camera_event_from_ws_frames,
    camera_update_from_ws_frames,
    event_from_ws_frames,
    process_camera,
)

_LOGGER = logging.getLogger(__name__)


class SecSpyServer:
    """Updates device states and attributes."""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str,
        password: str,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._base_url = f"http://{host}:{port}"
        self._token = b64encode(
            bytes(f"{self._username}:{self._password}", "utf-8")
        ).decode()
        self.headers = {"Content-Type": "text/xml"}
        self._is_authenticated = False
        self._last_device_update_time = 0
        self._last_websocket_check = 0
        self._device_state_machine = SecspyDeviceStateMachine()
        self._event_state_machine = SecspyEventStateMachine()

        self._processed_data = {}
        self.last_update_id = None

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

        if current_time - WEBSOCKET_CHECK_INTERVAL_SECONDS > self._last_websocket_check:
            _LOGGER.debug("Checking websocket")
            self._last_websocket_check = current_time
            await self.async_connect_ws()

        # If the websocket is connected/connecting
        # we do not need to get events
        if self.ws_connection or self._last_websocket_check == current_time:
            _LOGGER.debug("Skipping update since websocket is active")
            return self._processed_data if device_update else {}

    async def async_connect_ws(self):
        """Connect the websocket."""
        if self.ws_connection is not None:
            return

        if self.ws_task is not None:
            try:
                self.ws_task.cancel()
                self.ws_connection = None
            except Exception:
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
        if not self.ws_connection and "lastUpdateId" in json_response:
            self.last_update_id = json_response["lastUpdateId"]

        self._process_cameras_json(json_response, server_id, include_events)

        self._is_first_update = False

    async def get_snapshot_image(self, camera_id: str) -> bytes:
        """ Returns a Snapshot image from the specified Camera. """
        image_uri = f"http://{self._base_url}/image?cameraNum={camera_id}&width=1920&height=1080&quality=75&auth={self._token}"

        response = await self.req.get(
            image_uri,
            headers=self.headers,
        )
        if response.status != 200:
            raise RequestError(
                f"Fetching Snapshot Image failed: {response.status} - Reason: {response.reason}"
            )
        return await response.read()

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
                    self._port,
                    self._token,
                    camera,
                    include_events or self._is_first_update,
                ),
            )

    def _update_device(self, device_id, processed_update):
        """Update internal state of a device."""
        self._processed_data.setdefault(device_id, {}).update(processed_update)

    def _reset_device_events(self) -> None:
        """Reset device events between device updates."""
        for device_id in self._processed_data:
            self._update_device(device_id, PROCESSED_EVENT_EMPTY)

    async def _setup_websocket(self):
        """Setup the Event Websocket."""
        url = f"{self._base_url}/eventStream?version=3&format=multipart&auth={self._token}"
        if not self.ws_session:
            self.ws_session = aiohttp.ClientSession()
        _LOGGER.debug("WS connecting to: %s", url)

        async with self.ws_session.request("get", url) as self.ws_connection:
            async for msg in self.ws_connection.content:
                data = msg.decode("UTF-8").strip()
                try:
                    if data[:14].isnumeric():
                        self._process_ws_message(data)
                except Exception as err:
                    _LOGGER.exception(
                        "Error processing websocket message. Error: %s", err
                    )
                    return

    def subscribe_websocket(self, ws_callback):
        """Subscribe to websocket events.

        Returns a callback that will unsubscribe.
        """

        def _unsub_ws_callback():
            self._ws_subscriptions.remove(ws_callback)

        _LOGGER.debug("Adding subscription: %s", ws_callback)
        self._ws_subscriptions.append(ws_callback)
        return _unsub_ws_callback

    def _process_ws_message(self, msg):
        """Process websocket messages."""

        # pylint: disable=too-many-branches

        action_array = msg.split(" ")
        action_key = action_array[3]
        model_key = None
        if action_array[3] in CAMERA_MESSAGES:
            model_key = "camera"
        if action_array[3] in EVENT_MESSAGES:
            model_key = "event"

        if model_key not in ("event", "camera"):
            return

        action_json = {}
        data_json = {}

        if model_key == "event":
            if action_key == "FILE":
                data_json = {
                    "type": "motion",
                    "end": action_array[0],
                    "camera": action_array[2],
                    "file_name": action_array[4],
                    "isMotionDetected": False,
                }
                action_json = {
                    "modelKey": "event",
                    "action": "update",
                    "id": action_array[2],
                }

            if action_key == "CLASSIFY":
                action_json = {
                    "modelKey": "event",
                    "action": "update",
                    "id": action_array[2],
                }

                if len(action_array) > 6:
                    data_json = {
                        "type": "smart",
                        "camera": action_array[2],
                        action_array[4]: action_array[5],
                        action_array[6]: action_array[7],
                    }
                else:
                    human_score = action_array[5]
                    vehicle_score = 0
                    if "HUMAN" not in action_array:
                        human_score = 0
                        vehicle_score = action_array[5]
                    data_json = {
                        "type": "smart",
                        "camera": action_array[2],
                        "HUMAN": human_score,
                        "VEHICLE": vehicle_score,
                    }

            if action_key == "TRIGGER_M":
                data_json = {
                    "type": "motion",
                    "start": action_array[0],
                    "camera": action_array[2],
                    "reason": action_array[4],
                    "isMotionDetected": True,
                }
                action_json = {
                    "modelKey": "event",
                    "action": "add",
                    "id": action_array[2],
                }

            self._process_event_ws_message(action_json, data_json)
            return

        if model_key == "camera":
            action_json = {
                "modelKey": "camera",
                "id": action_array[2],
            }
            if action_key == "ARM_C":
                data_json = {
                    "recordingSettings": "always",
                }
            if action_key == "ARM_M":
                data_json = {
                    "recordingSettings": "motion",
                }
            if action_key in ("DISARM_C", "DISARM_M"):
                data_json = {
                    "recordingSettings": "never",
                }
            if action_key == "ONLINE":
                data_json = {
                    "online": True,
                }
            if action_key == "OFFLINE":
                data_json = {
                    "online": False,
                }

            self._process_camera_ws_message(action_json, data_json)
            return

        raise ValueError(f"Unexpected model key: {model_key}")

    def _process_camera_ws_message(self, action_json, data_json):
        """Process a decoded camera websocket message."""
        camera_id, processed_camera = camera_update_from_ws_frames(
            self._device_state_machine,
            self._host,
            self._port,
            self._token,
            action_json,
            data_json,
        )

        if camera_id is None:
            return
        _LOGGER.debug("Processed camera: %s", processed_camera)

        if processed_camera["recording_mode"] == "never":
            processed_event = camera_event_from_ws_frames(
                self._device_state_machine, action_json, data_json
            )
            if processed_event is not None:
                _LOGGER.debug("Processed camera event: %s", processed_event)
                processed_camera.update(processed_event)

        self.fire_event(camera_id, processed_camera)

    def _process_event_ws_message(self, action_json, data_json):
        """Process a decoded event websocket message."""
        device_id, processed_event = event_from_ws_frames(
            self._event_state_machine, action_json, data_json
        )

        if device_id is None:
            return

        _LOGGER.debug("Procesed event: %s", processed_event)

        self.fire_event(device_id, processed_event)

    def fire_event(self, device_id, processed_event):
        """Callback and event to the subscribers and update data."""
        self._update_device(device_id, processed_event)

        for subscriber in self._ws_subscriptions:
            subscriber({device_id: self._processed_data[device_id]})
