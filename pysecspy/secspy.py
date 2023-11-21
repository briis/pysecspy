"""This module contains the code to get Camera, NVR and streaming data from a SecuritySpy NVR."""
from __future__ import annotations

import abc
import datetime
import time
import json
import logging
import xmltodict

from typing import Any
from base64 import b64encode

import aiohttp
import asyncio

from .const import (
    CAMERA_KEYS,
    CAMERA_MESSAGES,
    DEFAULT_SNAPSHOT_HEIGHT,
    DEFAULT_SNAPSHOT_WIDTH,
    DEVICE_UPDATE_INTERVAL_SECONDS,
    EVENT_LENGTH_PRECISION,
    EVENT_MOTION,
    EVENT_MESSAGES,
    EVENT_SMART_DETECT_ZONE,
    KEY_CAMERA,
    KEY_EVENT,
    PROCESSED_EVENT_EMPTY,
    REASON_CODES,
    RECORDING_TYPE_ACTION,
    RECORDING_TYPE_CONTINUOUS,
    RECORDING_TYPE_MOTION,
    WEBSOCKET_CHECK_INTERVAL_SECONDS,
)

from .data import (
    SecSpyServerData,
    SecspyDeviceStateMachine,
    SecspyEventStateMachine,
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
    async def async_api_request( self, url: str, use_ssl: bool = False, process_json: bool = True) -> dict[str, Any]:
        """Override this."""
        raise NotImplementedError(
            "users must define async_api_request to use this base class"
        )

    @abc.abstractmethod
    async def async_api_post(self, url: str, post_data:dict[str, Any], use_ssl: bool = False) -> dict[str, Any]:
        """Override this."""
        raise NotImplementedError(
            "users must define async_api_request to use this base class"
        )

class SecuritySpyAPI(SecuritySpyAPIBase):
    """Default implementation for SecuritySpy api."""

    def __init__(self) -> None:
        """Init the API with or without session."""
        self.session = None

    async def async_api_request(self, url: str, use_ssl: bool = False, process_json: bool = True) -> dict[str, Any]:
        """Get data from SecuritySpy API."""

        _LOGGER.debug("URL CALLED: %s", url)

        is_new_session = False
        if self.session is None:
            self.session = aiohttp.ClientSession()
            is_new_session = True

        headers = {"Content-Type": "text/xml"}
        async with self.session.get(url, headers=headers, ssl=use_ssl) as response:
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

    async def async_api_post(self, url: str, post_data:dict[str, Any], use_ssl: bool = False) -> dict[str, Any]:
        """Get data from SecuritySpy API."""

        _LOGGER.debug("POST URL CALLED: %s", url)

        is_new_session = False
        if self.session is None:
            self.session = aiohttp.ClientSession()
            is_new_session = True

        headers = {"Content-Type": "text/xml"}
        async with self.session.post(url, headers=headers, data=post_data, ssl=use_ssl) as response:
            if response.status != 200:
                if is_new_session:
                    await self.session.close()
                raise RequestError(
                    f"Posting data failed: {response.status} - Reason: {response.reason}"
                )

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

        self._device_state_machine = SecspyDeviceStateMachine()
        self._event_state_machine = SecspyEventStateMachine()
        self._global_event_score_human = 0
        self._global_event_score_vehicle = 0
        self._global_event_score_animal = 0
        self._global_event_object = None
        self._is_first_update = True
        self._last_device_update_time = 0
        self._last_websocket_check = 0
        self._processed_data = {}
        self._server_credential = {
            "host": self._host,
            "port": self._port,
            "token": self._token,
        }
        if session:
            self._api.session = session

    @property
    def cameras(self) -> dict:
        """Return JSOn list of cameras and properties."""
        return self._processed_data

    @property
    def is_listening(self) -> bool:
        """Return if the client is listening for messages."""
        return self._ws_task is not None

#########################################
# MAIN LOOP FUNCTIONS
#########################################
    async def update(self, force_camera_update: bool = False) -> dict:
        """Update state of devices."""
        current_time = time.time()
        device_update = False
        if force_camera_update or (current_time - DEVICE_UPDATE_INTERVAL_SECONDS) > self._last_device_update_time:
            _LOGGER.debug("Updating devices...")
            device_update = True
            await self._get_devices(not self._ws_task)
            self._last_device_update_time = current_time

        if (current_time - WEBSOCKET_CHECK_INTERVAL_SECONDS) > self._last_websocket_check:
            _LOGGER.debug("Checking Websocket...")
            self._last_websocket_check = current_time
            await self.start_listening()

        if self._ws_task or self._last_websocket_check == current_time:
            _LOGGER.debug("Skip update, Websokcet is active")
            return self._processed_data if device_update else {}

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
        """Start Webserver stream listener."""
        assert self._ws_session
        while not self._ws_session.closed:
            async for msg in self._ws_stream.content:
                data = msg.decode("UTF-8").strip()
                self._process_message(data)

    def _process_message(self, data: str) -> None:
        try:
            if data[:14].isnumeric():
                action_array = data.split(" ")
                action_key = action_array[3]
                model_key = None
                if action_key in CAMERA_MESSAGES:
                    model_key = KEY_CAMERA
                if action_key in EVENT_MESSAGES:
                    model_key = KEY_EVENT
                if model_key is None:
                    return

                action_json = {}
                data_json = {}

                # Update when camera settings change
                if model_key == KEY_CAMERA:
                    action_json = {
                        "modelkey": KEY_CAMERA,
                        "id": action_array[2],
                    }
                    if action_key == "ARM_A":
                        data_json = {"recordingSettings_A": True}
                    if action_key == "ARM_C":
                        data_json = {"recordingSettings_C": True}
                    if action_key == "ARM_M":
                        data_json = {"recordingSettings_M": True}
                    if action_key == "DISARM_A":
                        data_json = {"recordingSettings_A": False}
                    if action_key == "DISARM_C":
                        data_json = {"recordingSettings_C": False}
                    if action_key == "DISARM_M":
                        data_json = {"recordingSettings_M": False}

                    self._process_camera_updates(action_json, data_json)
                    return

                # Update if a new event occurs
                if model_key == KEY_EVENT:
                    if action_key == "ONLINE":
                        data_json = {
                            "type": "online",
                            "camera": action_array[2],
                            "isOnline": True,
                        }
                        action_json = {
                            "modelKey": KEY_EVENT,
                            "action": "add",
                            "id": action_array[2],
                        }
                    if action_key == "OFFLINE":
                        data_json = {
                            "type": "online",
                            "camera": action_array[2],
                            "isOnline": False,
                        }
                        action_json = {
                            "modelKey": KEY_EVENT,
                            "action": "add",
                            "id": action_array[2],
                        }

                    if action_key == "TRIGGER_M":
                        self._global_event_object = action_array[4]
                        data_json = {
                            "type": "motion",
                            "start": action_array[0],
                            "camera": action_array[2],
                            "reason": self._global_event_object,
                            "event_score_human": self._global_event_score_human,
                            "event_score_vehicle": self._global_event_score_vehicle,
                            "isMotionDetected": True,
                            "isOnline": True,
                        }
                        action_json = {
                            "modelKey": KEY_EVENT,
                            "action": "add",
                            "id": action_array[2],
                        }

                    if action_key == "MOTION":
                        data_json = {
                            "type": "motion",
                            "start": action_array[0],
                            "camera": action_array[2],
                            "reason": self._global_event_object,
                            "event_score_human": self._global_event_score_human,
                            "event_score_vehicle": self._global_event_score_vehicle,
                            "isMotionDetected": True,
                            "isOnline": True,
                        }
                        action_json = {
                            "modelKey": KEY_EVENT,
                            "action": "add",
                            "id": action_array[2],
                        }

                    if action_key == "MOTION_END":
                        self._global_event_score_human = 0
                        self._global_event_score_vehicle = 0
                        self._global_event_object = None
                        data_json = {
                            "type": "motion",
                            "end": action_array[0],
                            "camera": action_array[2],
                            "isMotionDetected": False,
                            "reason": self._global_event_object,
                            "event_score_human": self._global_event_score_human,
                            "event_score_vehicle": self._global_event_score_vehicle,
                            "isOnline": True,
                        }
                        action_json = {
                            "modelKey": KEY_EVENT,
                            "action": "update",
                            "id": action_array[2],
                        }

                    if action_key == "CLASSIFY":
                        _LOGGER.debug("CLASSIFY: %s", action_array)
                        try:
                            self._global_event_score_human = action_array[5]
                            self._global_event_score_vehicle = action_array[7]
                            self._global_event_score_animal = action_array[9]
                            self._global_event_object = None
                        except Exception:
                            self._global_event_score_animal = 0
                        finally:
                            # Set the Event Object to the highest score
                            if (self._global_event_score_human > self._global_event_score_vehicle) and (self._global_event_score_human > self._global_event_score_animal):
                                self._global_event_object = "128"
                            if (self._global_event_score_vehicle > self._global_event_score_human) and (self._global_event_score_vehicle > self._global_event_score_animal):
                                self._global_event_object = "256"
                            if (self._global_event_score_animal > self._global_event_score_human) and (self._global_event_score_animal > self._global_event_score_vehicle):
                                self._global_event_object = "512"

                        data_json = {
                            "type": "motion",
                            "start": action_array[0],
                            "camera": action_array[2],
                            "reason": self._global_event_object,
                            "event_score_human": self._global_event_score_human,
                            "event_score_vehicle": self._global_event_score_vehicle,
                            "event_score_animal": self._global_event_score_animal,
                            "isOnline": True,
                        }
                        action_json = {
                            "modelKey": KEY_EVENT,
                            "action": "add",
                            "id": action_array[2],
                        }
                    self._process_event_updates(action_json, data_json)
                    return


        except Exception as err:
            _LOGGER.exception("STREAM: Error processing stream. Error: %s", err)
            return

        return

    def _process_timestamp(self, time_stamp: int):
        """Return timestamp formatted."""
        return datetime.datetime.strptime(time_stamp, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")

    def fire_event(self, device_id, processed_event):
        """Event callback and update data."""

        self._update_device(device_id, processed_event)

        for subscriber in self._ws_subscriptions:
            subscriber({device_id: self._processed_data[device_id]})


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
# CAMERA EVENT FUNCTIONS
#########################################

    def _process_camera_updates(self, action_json, data_json) -> None:
        """Process a decoded Camera Message."""

        camera_id, processed_camera = self._camera_from_updates(
            self._server_credential,
            action_json,
            data_json,
        )

        if camera_id is None:
            return

        if not processed_camera["recording_mode_m"]:
            processed_event = self._camera_event_from_updates(action_json, data_json)
            if processed_event is not None:
                _LOGGER.debug("Processed camera motion event: %s", processed_event)
                processed_camera.update(processed_event)

        if not processed_camera["recording_mode_c"]:
            processed_event = self._camera_event_from_updates(action_json, data_json)
            if processed_event is not None:
                _LOGGER.debug("Processed camera motion event: %s", processed_event)
                processed_camera.update(processed_event)

        if not processed_camera["recording_mode_a"]:
            processed_event = self._camera_event_from_updates(action_json, data_json)
            if processed_event is not None:
                _LOGGER.debug("Processed camera motion event: %s", processed_event)
                processed_camera.update(processed_event)

        self.fire_event(camera_id, processed_camera)

    def _camera_from_updates(self, server_credentials: str, action_json, data_json) -> None:
        """Convert camera data stream to internal format."""
        if action_json["modelKey"] != KEY_CAMERA:
            raise ValueError("Trigger must be a Camera")

        camera_id = action_json["id"]
        if not self._device_state_machine.has_device(camera_id):
            _LOGGER.debug("Skipping non-adopted camera: %s", data_json)
            return None, None

        camera = self._device_state_machine.update(camera_id, data_json)
        if data_json.keys().isdisjoint(CAMERA_KEYS):
            _LOGGER.debug("Skipping camera data: %s", data_json)
            return None, None

        _LOGGER.debug("Processing camera %s ...", camera)
        processed_camera = self._process_camera_data(None, server_credentials, camera, True)

        return camera_id, processed_camera

    def _camera_event_from_updates(self, action_json, data_json) -> None:
        """Create processed event from the camera model."""

        if "isMotionDetected" not in data_json and "timesincelastmotion" not in data_json and "isOnline" not in data_json:
            return None

        camera_id = action_json["id"]
        start_time = None
        event_length = 0
        event_on = False
        is_online = data_json.get("isOnline")

        last_motion = int(time.time()) + int(data_json["timesincelastmotion"])
        is_motion_detected = data_json.get("isMotionDetected")

        if is_motion_detected is None:
            start_time = self._device_state_machine.get_motion_detected_time(camera_id)
            event_on = True
        else:
            if is_motion_detected:
                event_on = True
                start_time = last_motion
                self._device_state_machine.set_motion_detected_time(camera_id, start_time)
            else:
                start_time = self._device_state_machine.get_motion_detected_time(camera_id)
                self._device_state_machine.set_motion_detected_time(camera_id, None)
                if last_motion is None:
                    last_motion = round(time.time() * 1000)

        if start_time is not None and last_motion is not None:
            event_length = round((float(last_motion) - float(start_time)) / 1000, EVENT_LENGTH_PRECISION)

        return {
            "event_on": event_on,
            "event_type": "motion",
            "event_start": start_time,
            "event_length": event_length,
            "event_online": is_online,
        }


    def _process_camera_data(self,server_id: str, server_credentials: str, camera, include_events: bool):
        """Process the Camera json data."""
        _camera_id = camera["number"]
        _camera_online = camera["connected"] == "yes"
        _camera_enabled = camera.get("enabled")
        _camera_ip_address = "Local" if camera["devicetype"] == "Local" else camera.get("address")
        # Recording Mode
        if camera.get("recordingSettings_A") is not None:
            _camera_recmode_a = camera.get("recordingSettings_A")
        else:
            _camera_recmode_a = camera["mode-a"] == "armed"
        if camera.get("recordingSettings_C") is not None:
            _camera_recmode_c = camera.get("recordingSettings_C")
        else:
            _camera_recmode_c = camera["mode-c"] == "armed"
        if camera.get("recordingSettings_M") is not None:
            _camera_recmode_m = camera.get("recordingSettings_M")
        else:
            _camera_recmode_m = camera["mode-m"] == "armed"
        # Live Image
        base_url = f"{server_credentials['host']}:{server_credentials['port']}"
        base_stream = f"rtsp://{base_url}/stream?auth={server_credentials['token']}"
        _camera_live_stream = f"{base_stream}&cameraNum={_camera_id}&codec=h264"
        # Jpeg Image
        image_width = str(camera["width"])
        image_height = str(camera["height"])
        _camera_latest_image = f"http://{base_url}/image?auth={server_credentials['token']}&cameraNum={_camera_id}&width={image_width}&height={image_height}&quality=75"
        # PTZ
        _camera_ptz_capabilities = camera.get("ptzcapabilities")
        _camera_preset_list = []
        if _camera_ptz_capabilities is not None and int(_camera_ptz_capabilities) > 0:
            # Build a list of PTZ Presets
            for preset in range(1, 10):
                if camera.get(f"preset-name-{preset}") is not None:
                    _camera_preset_list.append(camera.get(f"preset-name-{preset}"))

        camera_update = {
            "name": camera["name"],
            "type": "camera",
            "model": camera["devicename"],
            "online": _camera_online,
            "enabled": _camera_enabled,
            "recording_mode_a": _camera_recmode_a,
            "recording_mode_c": _camera_recmode_c,
            "recording_mode_m": _camera_recmode_m,
            "ip_address": _camera_ip_address,
            "live_stream": _camera_live_stream,
            "latest_image": _camera_latest_image,
            "image_width": image_width,
            "image_height": image_height,
            "fps": camera["current-fps"],
            "video_format": camera["video-format"],
            "ptz_capabilities": _camera_ptz_capabilities,
            "ptz_presets": _camera_preset_list,
        }

        if server_id is not None:
            camera_update["server_id"] = server_id

        if include_events:
            if camera.get("timesincelastmotion", None) is not None:
                last_update = int(time.time()) + int(camera["timesincelastmotion"])
                camera_update["last_motion"] = datetime.datetime.fromtimestamp(last_update / 1000).strftime("%Y-%m-%d %H:%M:%S")
            else:
                camera_update["last_motion"] = None

        return camera_update

#########################################
# MOTION EVENT FUNCTIONS
#########################################
    def _process_event_updates(self, action_json, data_json) -> None:
        """Process a decoded event websocket message."""

        device_id, processed_event = self._event_from_updates(action_json, data_json)
        if device_id is None:
            return

        _LOGGER.debug("Procesed event: %s", processed_event)

        self.fire_event(device_id, processed_event)

    def _event_from_updates(self, action_json, data_json) -> None:
        """Convert event data stream to internal format."""
        if action_json["modelKey"] != KEY_EVENT:
            raise ValueError("Trigger must be an event")

        action = action_json["action"]
        event_id = action_json["id"]

        if action == "add":
            device_id = data_json.get("camera")
            if device_id is None:
                return None, None
            self._event_state_machine.add(event_id, data_json)
            event = data_json
        elif action == "update":
            event = self._event_state_machine.update(event_id, data_json)
            if not event:
                return None, None
            device_id = event.get("camera")
        else:
            raise ValueError("Trigger action must be add or update")

        _LOGGER.debug("Processing Event %s", event)
        processed_event = self._process_event_data(event)

        return device_id, processed_event


    def _process_event_data(self, event):
        """Convert an event to our format."""
        start = event.get("start")
        end = event.get("end")
        event_type = event.get("type")
        event_reason = event.get("reason")
        event_online = event.get("isOnline")
        event_score_human = 0 if not event.get("event_score_human") else event.get("event_score_human")
        event_score_vehicle = 0 if not event.get("event_score_vehicle") else event.get("event_score_vehicle")
        event_score_animal = 0 if not event.get("event_score_animal") else event.get("event_score_animal")

        event_length = 0
        start_time = None

        if start:
            start_time = self._process_timestamp(start)
        if end:
            event_length = round(
                (float(end) / 1000) - (float(start) / 1000), EVENT_LENGTH_PRECISION
            )

        event_object = (
            "None" if event_reason not in REASON_CODES else REASON_CODES.get(event_reason)
        )

        processed_event = {
            "event_on": False,
            "event_type": event_type,
            "event_start": start_time,
            "event_length": event_length,
            "event_object": event_object,
            "event_score_human": event_score_human,
            "event_score_vehicle": event_score_vehicle,
            "event_score_animal": event_score_animal,
            "event_online": event_online,
        }

        if event_type in (EVENT_MOTION, EVENT_SMART_DETECT_ZONE):
            processed_event["last_motion"] = start_time
            if not end:
                processed_event["event_on"] = True

        return processed_event


#########################################
# INFORMATION FUNCTIONS
#########################################

    async def get_server_information(self) -> list[SecSpyServerData]:
        """Return list of Server data."""
        api_url =  f"{self._base_url}/systemInfo?auth={self._token}"
        xml_data = await self._api.async_api_request(api_url)

        return self._get_server_information(xml_data)

    async def _get_devices(self, include_events: bool) -> list[SecSpyServerData]:
        """Return list of Devices."""
        api_url =  f"{self._base_url}/systemInfo?auth={self._token}"
        xml_data = await self._api.async_api_request(api_url)
        server_id = xml_data["system"]["server"]["uuid"]

        self._process_cameras(xml_data, server_id, include_events)
        self._is_first_update = False


#########################################
# SETTING FUNCTIONS
#########################################

    async def set_arm_mode(self, camera_id: str, mode: str, enabled: bool) -> bool:
        """Set camera arming mode.

        Valid inputs for mode: action, on_motion, continuous.
        """

        _schedule = int(enabled)
        if mode in RECORDING_TYPE_ACTION:
            rec_mode = "A"
            json_id = "recording_mode_a"
        if mode in RECORDING_TYPE_MOTION:
            rec_mode = "M"
            json_id = "recording_mode_m"
        if mode in RECORDING_TYPE_CONTINUOUS:
            rec_mode = "C"
            json_id = "recording_mode_c"

        api_url = f"{self._base_url}/setSchedule?cameraNum={camera_id}&schedule={_schedule}&override=0&mode={rec_mode}&auth={self._token}"
        await self._api.async_api_request(api_url, process_json=False)

        self._processed_data[camera_id][json_id] = enabled
        return True

    async def enable_schedule_preset(self, schedule_id: str) -> bool:
        """Enable schedule preset.

        Valid inputs for schedule_id is a valid preset id.
        """

        api_url = f"{self._base_url}/setPreset?id={schedule_id}&auth={self._token}"
        await self._api.async_api_request(api_url, process_json=False)

        return True

    async def set_ptz_preset(self, camera_id: str, preset_id: str, speed: int=50) -> bool:
        """Set PTZ Preset."""

        api_url = f"{self._base_url}/ptz/command?cameraNum={camera_id}&command={preset_id}&speed={speed}&auth={self._token}"
        await self._api.async_api_request(api_url, process_json=False)

        return True

    async def enable_camera(self, camera_id: str, enabled: bool) -> bool:
        """Enable or disables camera."""

        _enable = int(enabled)

        api_url = f"{self._base_url}/camerasettings?auth={self._token}"
        data = f"cameraNum={camera_id}&camEnabledCheck={_enable}&action=save"
        await self._api.async_api_post(api_url,post_data=data)

        self._processed_data[camera_id]["enabled"] = enabled
        return True

#########################################
# SERVICE CALLS
#########################################

    async def get_snapshot_image(self, camera_id: str, width: int | None = None, height: int | None = None) -> bytes:
        """Return Snapshot image from the specified Camera."""
        image_width = width or DEFAULT_SNAPSHOT_WIDTH
        image_height = height or DEFAULT_SNAPSHOT_HEIGHT

        api_url = f"{self._base_url}/image?cameraNum={camera_id}&width={image_width}&height={image_height}&quality=75&auth={self._token}"
        return await self._api.async_api_request(api_url, self._use_ssl, False)

    async def get_latest_motion_recording(self, camera_id: str) -> bytes:
        """Return the latest motion recording file."""

        # Get the latest file name
        file_url = f"{self._base_url}/download?cameraNum={camera_id}&mcFilesCheck=1&ageText=1&results=1&format=xml&auth={self._token}"
        json_data = await self._api.async_api_request(file_url)
        download_url = json_data["feed"]["entry"]["link"]["@href"]

        # Retrieve the file
        api_url = f"{self._base_url}/{download_url}?auth={self._token}"
        return await self._api.async_api_request(api_url, self._use_ssl, False)

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

    def _process_cameras(self, api_result, server_id: str, include_events: bool) -> None:
        """Process camera data and updates."""
        items = api_result["system"]["cameralist"]["camera"]
        cameras = []

        if not isinstance(items, frozenset | list | set | tuple,):
            cameras.append(items)
        else:
            cameras = items

        for camera in cameras:
            camera_id = camera["number"]
            _LOGGER.debug("Processing camera id: %s", camera_id)
            if self._is_first_update:
                self._update_device(camera_id, PROCESSED_EVENT_EMPTY)
                camera["enabled"] = True
            self._device_state_machine.update(camera_id, camera)
            self._update_device(
                camera_id,
                self._process_camera_data(
                    server_id,
                    self._server_credential,
                    camera,
                    include_events or self._is_first_update
                )
            )

    def _update_device(self, device_id, processed_update):
        """Update internal state of a device."""
        self._processed_data.setdefault(device_id, {}).update(processed_update)
