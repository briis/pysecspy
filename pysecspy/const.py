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
EVENT_MESSAGES = ["TRIGGER_M", "FILE", "MOTION"]

RECORDING_TYPE_ACTION = "action"
RECORDING_TYPE_MOTION = "on_motion"
RECORDING_TYPE_CONTINUOUS = "continuous"

RECORDING_MODE_LIST = {
    RECORDING_TYPE_MOTION: "M",
    RECORDING_TYPE_CONTINUOUS: "C",
}

SERVER_ID = "server_id"
SERVER_NAME = "server_name"
