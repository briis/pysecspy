"""Constant definitions for SecSpy Wrapper."""

DEVICE_UPDATE_INTERVAL_SECONDS = 60
WEBSOCKET_CHECK_INTERVAL_SECONDS = 120

CAMERA_MESSAGES = [
    "ARM_A",
    "DISARM_A",
    "ARM_C",
    "DISARM_C",
    "ARM_M",
    "DISARM_M",
    "OFFLINE",
    "ONLINE",
]
EVENT_MESSAGES = ["TRIGGER_M", "MOTION", "CLASSIFY", "MOTION_END"]

RECORDING_TYPE_ACTION = "action"
RECORDING_TYPE_MOTION = "on_motion"
RECORDING_TYPE_CONTINUOUS = "continuous"

RECORDING_MODE_LIST = {
    RECORDING_TYPE_MOTION: "M",
    RECORDING_TYPE_CONTINUOUS: "C",
}

SERVER_ID = "server_id"
SERVER_NAME = "server_name"

PTZ_CAPABILITIES = {
    "0": "No PTX Capabilities",
    "1": "Pan and Tilt",
    "2": "Home",
    "3": "Pan and Tilt, Home",
    "4": "Zoom",
    "5": "Pan and Tilt, Zoom",
    "6": "Home, Zoom",
    "7": "Pan and Tilt, Home, Zoom",
    "8": "Presets",
    "9": "Pand and Tilt, Presets",
    "10": "Home, Presets",
    "11": "Pan and Tilt, Home, Presets",
    "16": "Continuous movement",
}