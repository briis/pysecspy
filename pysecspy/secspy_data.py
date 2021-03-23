"""SecuritySpy Data."""
import logging
import struct
from collections import OrderedDict

_LOGGER = logging.getLogger(__name__)

MAX_SUPPORTED_CAMERAS = 256
MAX_EVENT_HISTORY_IN_STATE_MACHINE = MAX_SUPPORTED_CAMERAS * 2

PROCESSED_EVENT_EMPTY = {
    "event_start": None,
    "event_on": False,
    "event_ring_on": False,
    "event_type": None,
    "event_length": 0,
    "event_object": [],
}


def process_camera(server_id, host, camera, include_events):
    """Process the camera xml."""
    
    # If addtional keys are checked, update CAMERA_KEYS

    # Get if camera is online
    online = camera["connected"] == "yes"
    # Get Recording Mode
    # recording_mode = str(camera["recordingSettings"]["mode"])
    # # Get Infrared Mode
    # ir_mode = str(camera["ispSettings"]["irLedMode"])
    # # Get Status Light Setting
    # status_light = camera["ledSettings"]["isEnabled"]

    # # Get when the camera came online
    # upsince = (
    #     "Offline"
    #     if camera["upSince"] is None
    #     else datetime.datetime.fromtimestamp(int(camera["upSince"]) / 1000).strftime(
    #         "%Y-%m-%d %H:%M:%S"
    #     )
    # )
    # # Check if Regular Camera or Doorbell
    # device_type = (
    #     "camera" if "doorbell" not in str(camera["type"]).lower() else "doorbell"
    # )
    # # Get Firmware Version
    # firmware_version = str(camera["firmwareVersion"])

    # # Get High FPS Video Mode
    # featureflags = camera.get("featureFlags")
    # has_highfps = "highFps" in featureflags.get("videoModes", "")
    # video_mode = camera.get("videoMode") or "default"
    # # Get HDR Mode
    # has_hdr = featureflags.get("hasHdr")
    # hdr_mode = camera.get("hdrMode") or False
    # # Doorbell Chime
    # has_chime = featureflags.get("hasChime")
    # chime_enabled = camera.get("chimeDuration") not in CHIME_DISABLED
    # chime_duration = camera.get("chimeDuration")
    # # Get Microphone Volume
    # mic_volume = camera.get("micVolume") or 0
    # # Get SmartDetect capabilities
    # has_smartdetect = featureflags.get("hasSmartDetect")
    # # Get if soroundings are Dark
    # is_dark = camera.get("isDark") or False
    # # Get Optical Zom capabilities
    # has_opticalzoom = featureflags.get("canOpticalZoom")
    # zoom_position = str(camera["ispSettings"]["zoomPosition"])
    # # Wide Dynamic Range
    # wdr = str(camera["ispSettings"]["wdr"])
    # # Get Privacy Mode
    # privacyzones = camera.get("privacyZones")
    # privacy_on = False
    # for row in privacyzones:
    #     if row["name"] == ZONE_NAME:
    #         privacy_on = row["points"] == PRIVACY_ON
    #         break

    # # Add rtsp streaming url if enabled
    # rtsp = None
    # channels = camera["channels"]
    # for channel in channels:
    #     if channel["isRtspEnabled"]:
    #         rtsp = f"rtsp://{host}:7447/{channel['rtspAlias']}"
    #         break

    # camera_update = {
    #     "name": str(camera["name"]),
    #     "type": camera["devicetype"],
    #     "model": str(camera["type"]),
    #     "mac": str(camera["mac"]),
    #     "ip_address": str(camera["host"]),
    #     "firmware_version": firmware_version,
    #     "recording_mode": recording_mode,
    #     "ir_mode": ir_mode,
    #     "status_light": status_light,
    #     "rtsp": rtsp,
    #     "up_since": upsince,
    #     "online": online,
    #     "has_highfps": has_highfps,
    #     "has_hdr": has_hdr,
    #     "video_mode": video_mode,
    #     "hdr_mode": hdr_mode,
    #     "mic_volume": mic_volume,
    #     "has_smartdetect": has_smartdetect,
    #     "is_dark": is_dark,
    #     "privacy_on": privacy_on,
    #     "has_opticalzoom": has_opticalzoom,
    #     "zoom_position": zoom_position,
    #     "wdr": wdr,
    #     "has_chime": has_chime,
    #     "chime_enabled": chime_enabled,
    #     "chime_duration": chime_duration,
    # }
    camera_update = {
        "name": str(camera["name"]),
        "type": camera["devicetype"],
        "model": str(camera["devicename"]),
        "online": online,
    }

    if server_id is not None:
        camera_update["server_id"] = server_id
    # if include_events:
    #     # Get the last time motion occured
    #     camera_update["last_motion"] = (
    #         None
    #         if camera["lastMotion"] is None
    #         else datetime.datetime.fromtimestamp(
    #             int(camera["lastMotion"]) / 1000
    #         ).strftime("%Y-%m-%d %H:%M:%S")
    #     )
    #     # Get the last time doorbell was ringing
    #     camera_update["last_ring"] = (
    #         None
    #         if camera.get("lastRing") is None
    #         else datetime.datetime.fromtimestamp(
    #             int(camera["lastRing"]) / 1000
    #         ).strftime("%Y-%m-%d %H:%M:%S")
    #     )

    return camera_update

def event_from_ws_frames(state_machine, action_json, data_json):
    """Convert a websocket frame to internal format.

    Smart Detect Event Add:
    {'action': 'add', 'newUpdateId': '032615bb-910d-41bf-8710-b04959f24455', 'modelKey': 'event', 'id': '5fb0c89003085203870013d0'}
    {'type': 'smartDetectZone', 'start': 1605421197481, 'score': 98, 'smartDetectTypes': ['person'], 'smartDetectEvents': [], 'camera': '5f9f43f102f7d90387004da5', 'partition': None, 'id': '5fb0c89003085203870013d0', 'modelKey': 'event'}

    Smart Detect Event Update:
    {'action': 'update', 'newUpdateId': '84c74562-bb14-4426-8b92-84ae80d1fb4a', 'modelKey': 'event', 'id': '5fb0c92303b75203870013db'}
    {'end': 1605421366608, 'score': 52}

    Camera Motion Start (event):
    {'action': 'add', 'newUpdateId': '25b1142a-2d0d-4b85-b97e-401b03dd1f0b', 'modelKey': 'event', 'id': '5fb0c90603455203870013d7'}
    {'type': 'motion', 'start': 1605421315759, 'score': 0, 'smartDetectTypes': [], 'smartDetectEvents': [], 'camera': '5e539ed503617003870003ed', 'partition': None, 'id': '5fb0c90603455203870013d7', 'modelKey': 'event'}

    Camera Motion End (event):
    {'action': 'update', 'newUpdateId': 'aa1c159c-c575-443a-9e57-b63ed847549c', 'modelKey': 'event', 'id': '5fb0c90603455203870013d7'}
    {'end': 1605421330342, 'score': 46}

    Camera Ring (event)
    {'action': 'add', 'newUpdateId': 'da36377d-b947-4b05-ba11-c17b0d2703f9', 'modelKey': 'event', 'id': '5fb1964b03b352038700184d'}
    {'type': 'ring', 'start': 1605473867945, 'end': 1605473868945, 'score': 0, 'smartDetectTypes': [], 'smartDetectEvents': [], 'camera': '5f9f43f102f7d90387004da5', 'partition': None, 'id': '5fb1964b03b352038700184d', 'modelKey': 'event'}

    Light Motion (event)
    {'action': 'update', 'newUpdateId': '41fddb04-e79f-4726-945f-0de74294045e', 'modelKey': 'light', 'id': '5fec968501ce7d038700539b'}
    {'isPirMotionDetected': True, 'lastMotion': 1609579367419}
    """

    if action_json["modelKey"] != "event":
        raise ValueError("Model key must be event")

    action = action_json["action"]
    event_id = action_json["id"]

    if action == "add":
        device_id = (
            data_json.get("camera") or data_json.get("light") or data_json.get("sensor")
        )
        if device_id is None:
            return None, None
        state_machine.add(event_id, data_json)
        event = data_json
    elif action == "update":
        event = state_machine.update(event_id, data_json)
        if not event:
            return None, None
        device_id = event.get("camera") or event.get("light") or data_json.get("sensor")
    else:
        raise ValueError("The action must be add or update")

    _LOGGER.debug("Processing event: %s", event)
    processed_event = process_event(event, minimum_score, LIVE_RING_FROM_WEBSOCKET)

    return device_id, processed_event


def process_event(event):
    """Convert an event to our format."""
    start = event.get("start")
    end = event.get("end")
    event_type = event.get("type")
    score = event.get("score")

    event_length = 0
    start_time = None

    if start:
        start_time = _process_timestamp(start)
    if end:
        event_length = round(
            (float(end) / 1000) - (float(start) / 1000), EVENT_LENGTH_PRECISION
        )

    processed_event = {
        "event_on": False,
        "event_ring_on": False,
        "event_type": event_type,
        "event_start": start_time,
        "event_length": event_length,
        "event_score": score,
        "event_object": event.get("smartDetectTypes"),
    }

    if event_type in (EVENT_MOTION, EVENT_SMART_DETECT_ZONE):
        processed_event["last_motion"] = start_time
        if score is not None and int(score) >= minimum_score and not end:
            processed_event["event_on"] = True
    elif event_type == EVENT_RING:
        processed_event["last_ring"] = start_time
        if ring_interval == LIVE_RING_FROM_WEBSOCKET or not end:
            _LOGGER.debug("EVENT: DOORBELL IS RINGING")
            processed_event["event_ring_on"] = True
        elif start >= ring_interval and end >= ring_interval:
            _LOGGER.debug("EVENT: DOORBELL HAS RUNG IN LAST 3 SECONDS!")
            processed_event["event_ring_on"] = True
        else:
            _LOGGER.debug("EVENT: DOORBELL WAS NOT RUNG IN LAST 3 SECONDS")

    thumbail = event.get("thumbnail")
    if thumbail is not None:  # Only update if there is a new Motion Event
        processed_event["event_thumbnail"] = thumbail

    heatmap = event.get("heatmap")
    if heatmap is not None:  # Only update if there is a new Motion Event
        processed_event["event_heatmap"] = heatmap

    return processed_event


class SecspyDeviceStateMachine:
    """A simple state machine for events."""

    def __init__(self):
        """Init the state machine."""
        self._devices = {}
        self._motion_detected_time = {}

    def has_device(self, device_id):
        """Check to see if a device id is in the state machine."""
        return device_id in self._devices

    def update(self, device_id, new_json):
        """Update an device in the state machine."""
        self._devices.setdefault(device_id, {}).update(new_json)
        return self._devices[device_id]

    def set_motion_detected_time(self, device_id, timestamp):
        """Set device motion start detected time."""
        self._motion_detected_time[device_id] = timestamp

    def get_motion_detected_time(self, device_id):
        """Get device motion start detected time."""
        return self._motion_detected_time.get(device_id)


class SecspyEventStateMachine:
    """A simple state machine for cameras."""

    def __init__(self):
        """Init the state machine."""
        self._events = FixSizeOrderedDict(max_size=MAX_EVENT_HISTORY_IN_STATE_MACHINE)

    def add(self, event_id, event_json):
        """Add an event to the state machine."""
        self._events[event_id] = event_json

    def update(self, event_id, new_event_json):
        """Update an event in the state machine and return the merged event."""
        event_json = self._events.get(event_id)
        if event_json is None:
            return None
        event_json.update(new_event_json)
        return event_json


class FixSizeOrderedDict(OrderedDict):
    """A fixed size ordered dict."""

    def __init__(self, *args, max_size=0, **kwargs):
        """Create the FixSizeOrderedDict."""
        self._max_size = max_size
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        """Set an update up to the max size."""
        OrderedDict.__setitem__(self, key, value)
        if self._max_size > 0:
            if len(self) > self._max_size:
                self.popitem(False)
