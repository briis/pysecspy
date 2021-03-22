"""SecuritySpy Data."""

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
