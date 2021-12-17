"""Module to communicate with the SecuritySpy API."""
import asyncio
import json as pjson
import logging
import time
from base64 import b64encode
from typing import Optional

import aiohttp
import xmltodict
from aiohttp import client_exceptions

from pysecspy.const import (
    CAMERA_MESSAGES,
    DEVICE_UPDATE_INTERVAL_SECONDS,
    EVENT_MESSAGES,
    RECORDING_TYPE_ACTION,
    RECORDING_TYPE_CONTINUOUS,
    RECORDING_TYPE_MOTION,
    SERVER_ID,
    SERVER_NAME,
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

DEFAULT_SNAPSHOT_WIDTH = 1920
DEFAULT_SNAPSHOT_HEIGHT = 1080

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
        use_ssl: bool = False,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._base_url = (
            f"https://{host}:{port}" if self._use_ssl else f"http://{host}:{port}"
        )
        self._token = b64encode(
            bytes(f"{self._username}:{self._password}", "utf-8")
        ).decode()
        self.headers = {"Content-Type": "text/xml"}
        self._last_device_update_time = 0
        self._last_websocket_check = 0
        self._device_state_machine = SecspyDeviceStateMachine()
        self._event_state_machine = SecspyEventStateMachine()
        self.server_credential = {
            "host": self._host,
            "port": self._port,
            "token": self._token,
        }

        self._processed_data = {}
        self.last_update_id = None

        self.req = session
        self.headers = None
        self.ws_session = None
        self.ws_connection = None
        self.ws_task = None
        self._ws_subscriptions = []
        self._is_first_update = True
        self._signal_stop = False

    @property
    def devices(self):
        """ Returns a JSON formatted list of Devices. """
        return self._processed_data

    async def update(self, force_camera_update=False) -> dict:
        """Updates the status of devices."""

        current_time = time.time()
        device_update = False
        if (
            force_camera_update
            or (current_time - DEVICE_UPDATE_INTERVAL_SECONDS)
            > self._last_device_update_time
        ):
            _LOGGER.debug("Doing device update")
            device_update = True
            await self._get_device_list(not self.ws_connection)
            self._last_device_update_time = current_time
        else:
            _LOGGER.debug("Skipping device update")

        if (
            current_time - WEBSOCKET_CHECK_INTERVAL_SECONDS
        ) > self._last_websocket_check:
            _LOGGER.debug("Checking websocket")
            self._last_websocket_check = current_time
            await self.async_connect_ws()

        if self.ws_connection or self._last_websocket_check == current_time:
            _LOGGER.debug("Skipping update since websocket is active.")
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
        self.ws_task = asyncio.ensure_future(self._setup_streamreader())

    async def async_disconnect_ws(self):
        """Disconnect the websocket."""
        if self.ws_connection is None:
            return

        await self.ws_connection.wait_for_close()
        await self.ws_session.close()

    async def _get_device_list(self, include_events) -> None:
        """Get a list of devices connected to the NVR."""

        system_uri = f"{self._base_url}/systemInfo?auth={self._token}"
        response = await self.req.get(
            system_uri,
            headers=self.headers,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Fetching Camera List failed: {response.status} - Reason: {response.reason}"
            )
        data = await response.read()
        json_raw = xmltodict.parse(data)
        json_response = pjson.loads(pjson.dumps(json_raw))
        server_id = json_response["system"]["server"]["uuid"]

        self._process_cameras_json(json_response, server_id, include_events)

        self._is_first_update = False

    async def _get_server_information(self) -> None:
        """Return information about the SecuritySpy Server."""

        system_uri = f"{self._base_url}/systemInfo?auth={self._token}"
        response = await self.req.get(
            system_uri,
            headers=self.headers,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Fetching Server Information failed: {response.status} - Reason: {response.reason}"
            )

        data = await response.read()
        json_raw = xmltodict.parse(data)
        json_response = pjson.loads(pjson.dumps(json_raw))
        nvr = json_response["system"]["server"]
        sys_info = json_response["system"]
        sched_preset = sys_info.get("schedulepresetlist")
        presets = []
        if sched_preset is not None:
            for preset in sched_preset["schedulepreset"]:
                presets.append(preset)

        return {
            SERVER_NAME: nvr["server-name"],
            "server_version": nvr["version"],
            SERVER_ID: nvr["uuid"],
            "server_ip_address": nvr["ip1"],
            "schedule_presets": presets,
            "server_port": self._port,
        }

    async def get_unique_id(self) -> None:
        """Get a Unique ID for this NVR."""

        return await self._get_server_information()[SERVER_ID]

    async def get_server_information(self):
        """Returns a Server Information for this NVR."""
        return await self._get_server_information()

    async def get_snapshot_image(self, camera_id: str, width: Optional[int] = None, height: Optional[int] = None) -> bytes:
        """ Returns a Snapshot image from the specified Camera. """
        image_width = width or DEFAULT_SNAPSHOT_WIDTH
        image_height = height or DEFAULT_SNAPSHOT_HEIGHT

        image_uri = f"{self._base_url}/image?cameraNum={camera_id}&width={image_width}&height={image_height}&quality=75&auth={self._token}"
        _LOGGER.debug(image_uri)

        response = await self.req.get(
            image_uri,
            headers=self.headers,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Fetching Snapshot Image failed: {response.status} - Reason: {response.reason}"
            )
        return await response.read()

    async def get_latest_motion_recording(self, camera_id: str) -> bytes:
        """ Returns the latest motion recording file. """

        # Get the latest file name
        file_uri = f"{self._base_url}/download?cameraNum={camera_id}&mcFilesCheck=1&ageText=1&results=1&format=xml&auth={self._token}"
        response = await self.req.get(
            file_uri,
            headers=self.headers,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Fetching Recording files failed: {response.status} - Reason: {response.reason}"
            )
        json_raw = xmltodict.parse(await response.read())
        json_response = pjson.loads(pjson.dumps(json_raw))
        download_url = json_response["feed"]["entry"]["link"]["@href"]

        # Retrieve the file
        video_uri = f"{self._base_url}/{download_url}?auth={self._token}"
        _LOGGER.debug("VIDEO URI: %s", video_uri)

        response = await self.req.get(
            video_uri,
            headers=self.headers,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Fetching Video Recording failed: {response.status} - Reason: {response.reason}"
            )
        return await response.read()

    async def set_arm_mode(self, camera_id: str, mode: str, enabled: bool) -> bool:
        """Sets the camera arming mode .
        Valid inputs for mode: action, on_motion, continuous. Valid input for value is True or False
        """

        schedule = 1 if enabled else 0

        if mode in RECORDING_TYPE_ACTION:
            rec_mode = "A"
            json_id = "recording_mode_a"

        if mode in RECORDING_TYPE_MOTION:
            rec_mode = "M"
            json_id = "recording_mode_m"

        if mode in RECORDING_TYPE_CONTINUOUS:
            rec_mode = "C"
            json_id = "recording_mode_c"

        cam_uri = f"{self._base_url}/setSchedule?cameraNum={camera_id}&schedule={schedule}&override=0&mode={rec_mode}&auth={self._token}"

        response = await self.req.get(
            cam_uri,
            headers=self.headers,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Setting Arming mode failed: {response.status} - Reason: {response.reason}"
            )

        self._processed_data[camera_id][json_id] = enabled
        return True

    async def enable_schedule_preset(self, schedule_id: str) -> bool:
        """Enables a schedule preset.
        Valid inputs for schedule_id is a valid preset id
        Format: setPreset?id=X
        """

        cam_uri = f"{self._base_url}/setPreset?id={schedule_id}&auth={self._token}"

        response = await self.req.get(
            cam_uri,
            headers=self.headers,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Setting Schedule Preset failed: {response.status} - Reason: {response.reason}"
            )

        return True

    async def set_ptz_preset(self, camera_id: str, preset_id: str, speed: int=50) -> bool:
        """Set a PTZ Preset."""
        cam_uri = f"{self._base_url}/ptz/command?cameraNum={camera_id}&command={preset_id}&speed={speed}&auth={self._token}"

        response = await self.req.get(
            cam_uri,
            headers=self.headers,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Setting PTZ Preset failed: {response.status} - Reason: {response.reason}"
            )

        return True

    async def enable_camera(self, camera_id: str, enabled: bool) -> bool:
        """Enables or disables the camera.
        Valid input for enabled is True or False
        """

        _enable = 1 if enabled else 0

        cam_uri = f"{self._base_url}/camerasettings?auth={self._token}"
        data = f"cameraNum={camera_id}&camEnabledCheck={_enable}&action=save"

        response = await self.req.post(
            cam_uri,
            headers=self.headers,
            data=data,
            ssl=False,
        )
        if response.status != 200:
            raise RequestError(
                f"Enable/Disable camera failed: {response.status} - Reason: {response.reason}"
            )

        self._processed_data[camera_id]["enabled"] = enabled
        return True

    def _process_cameras_json(self, json_response, server_id, include_events):
        items = json_response["system"]["cameralist"]["camera"]
        cameras = []
        if not isinstance(
            items,
            (
                frozenset,
                list,
                set,
                tuple,
            ),
        ):
            cameras.append(items)
        else:
            cameras = items

        for camera in cameras:
            camera_id = camera["number"]
            _LOGGER.debug("Processing Camera %s", camera_id)
            if self._is_first_update:
                self._update_device(camera_id, PROCESSED_EVENT_EMPTY)
                camera["enabled"] = True
            self._device_state_machine.update(camera_id, camera)
            self._update_device(
                camera_id,
                process_camera(
                    server_id,
                    self.server_credential,
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

    async def _setup_streamreader(self):
        """Setup the Event Websocket."""
        url = f"{self._base_url}/eventStream?version=3&format=multipart&auth={self._token}"
        timeout = aiohttp.ClientTimeout(
            total=None, connect=None, sock_connect=None, sock_read=None
        )
        if not self.ws_session:
            self.ws_session = aiohttp.ClientSession(timeout=timeout)
        _LOGGER.debug("Receiving from: %s", url)

        self.ws_connection = await self.ws_session.request("get", url)
        try:
            async for msg in self.ws_connection.content:
                if self.ws_connection.closed:
                    break
                data = msg.decode("UTF-8").strip()
                if data[:14].isnumeric():
                    try:
                        self._process_ws_message(data)
                    except Exception as err:
                        _LOGGER.exception(
                            "Error processing stream message. Error: %s", err
                        )
                        return
                await asyncio.sleep(0)
        except client_exceptions.ClientConnectionError:
            return
        except Exception as ed:
            _LOGGER.debug("Unhandled error: %s", ed)
            return
        finally:
            _LOGGER.debug("stream disconnected")
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

    def _process_ws_message(self, msg):
        """Process websocket messages."""

        # pylint: disable=too-many-branches

        action_array = msg.split(" ")
        action_key = action_array[3]
        _LOGGER.debug("ACTION KEY: %s", action_key)
        model_key = None
        if action_key in CAMERA_MESSAGES:
            model_key = "camera"
        if action_key in EVENT_MESSAGES:
            model_key = "event"

        if model_key not in ("event", "camera"):
            return

        action_json = {}
        data_json = {}

        if model_key == "camera":
            action_json = {
                "modelKey": "camera",
                "id": action_array[2],
            }
            if action_key == "ARM_A":
                data_json = {
                    "recordingSettings_A": True,
                }
            if action_key == "ARM_C":
                data_json = {
                    "recordingSettings_C": True,
                }
            if action_key == "ARM_M":
                data_json = {
                    "recordingSettings_M": True,
                }
            if action_key == "DISARM_A":
                data_json = {
                    "recordingSettings_A": False,
                }
            if action_key == "DISARM_C":
                data_json = {
                    "recordingSettings_C": False,
                }
            if action_key == "DISARM_M":
                data_json = {
                    "recordingSettings_M": False,
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

        if model_key == "event":

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

            if action_key == "MOTION":
                data_json = {
                    "type": "motion",
                    "start": action_array[0],
                    "camera": action_array[2],
                    "isMotionDetected": True,
                }
                action_json = {
                    "modelKey": "event",
                    "action": "add",
                    "id": action_array[2],
                }

            if action_key == "MOTION_END":
                data_json = {
                    "type": "motion",
                    "end": action_array[0],
                    "camera": action_array[2],
                    "isMotionDetected": False,
                }
                action_json = {
                    "modelKey": "event",
                    "action": "update",
                    "id": action_array[2],
                }

            if action_key == "CLASSIFY":
                # Can contain both HUMAN and VEHICLE
                if len(action_array) > 6:
                    human_score = action_array[5]
                    vehicle_score = action_array[7]
                    reason_code = "128" if human_score > vehicle_score else "256"
                else:
                    reason_code = "128"
                    if "HUMAN" not in action_array:
                        reason_code = "256"

                data_json = {
                    "type": "motion",
                    "start": action_array[0],
                    "camera": action_array[2],
                    "reason": reason_code,
                    "isMotionDetected": True,
                }
                action_json = {
                    "modelKey": "event",
                    "action": "add",
                    "id": action_array[2],
                }

            self._process_event_ws_message(action_json, data_json)
            return

        raise ValueError(f"Unexpected model key: {model_key}")

    def _process_camera_ws_message(self, action_json, data_json):
        """Process a decoded camera websocket message."""
        camera_id, processed_camera = camera_update_from_ws_frames(
            self._device_state_machine,
            self.server_credential,
            action_json,
            data_json,
        )

        if camera_id is None:
            return
        # _LOGGER.debug("Processed camera: %s", processed_camera)

        if not processed_camera["recording_mode_m"]:
            processed_event = camera_event_from_ws_frames(
                self._device_state_machine, action_json, data_json
            )
            if processed_event is not None:
                _LOGGER.debug("Processed camera motion event: %s", processed_event)
                processed_camera.update(processed_event)
        if not processed_camera["recording_mode_c"]:
            processed_event = camera_event_from_ws_frames(
                self._device_state_machine, action_json, data_json
            )
            if processed_event is not None:
                _LOGGER.debug("Processed camera continuous event: %s", processed_event)
                processed_camera.update(processed_event)
        if not processed_camera["recording_mode_a"]:
            processed_event = camera_event_from_ws_frames(
                self._device_state_machine, action_json, data_json
            )
            if processed_event is not None:
                _LOGGER.debug("Processed camera action event: %s", processed_event)
                processed_camera.update(processed_event)

        self.fire_event(camera_id, processed_camera)

    def _process_event_ws_message(self, action_json, data_json):
        """Process a decoded event websocket message."""
        device_id, processed_event = event_from_ws_frames(
            self._event_state_machine, action_json, data_json
        )

        if device_id is None:
            return

        # _LOGGER.debug("Procesed event: %s", processed_event)

        self.fire_event(device_id, processed_event)

    def fire_event(self, device_id, processed_event):
        """Callback and event to the subscribers and update data."""
        self._update_device(device_id, processed_event)

        for subscriber in self._ws_subscriptions:
            subscriber({device_id: self._processed_data[device_id]})
