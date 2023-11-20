"""Constant definitions for SecSpy Wrapper."""
from __future__ import annotations

CAMERA_KEYS = {
    "state",
    "recordingSettings_A",
    "recordingSettings_C",
    "recordingSettings_M",
    "recording_mode_a",
    "recording_mode_c",
    "recording_mode_m",
    "isOnline",
    "enabled",
    "reason",
    "lastMotion",
    "isMotionDetected",
}
CAMERA_MESSAGES = [
    "ARM_A",
    "DISARM_A",
    "ARM_C",
    "DISARM_C",
    "ARM_M",
    "DISARM_M",
]

DEFAULT_SNAPSHOT_WIDTH = 1920
DEFAULT_SNAPSHOT_HEIGHT = 1080
DEVICE_UPDATE_INTERVAL_SECONDS = 60

EVENT_DISCONNECT = "disconnect"
EVENT_LENGTH_PRECISION = 3
EVENT_MESSAGES = ["TRIGGER_M", "MOTION", "CLASSIFY", "MOTION_END", "ONLINE", "OFFLINE"]
EVENT_MOTION = "motion"
EVENT_SMART_DETECT_ZONE = "smart"

KEY_CAMERA = "camera"
KEY_EVENT = "event"

PROCESSED_EVENT_EMPTY = {
    "event_start": None,
    "event_on": False,
    "event_type": None,
    "event_online": True,
    "event_length": 0,
    "event_object": None,
    "event_score_human": 0,
    "event_score_vehicle": 0,
    "event_score_animal": 0,
}

REASON_CODES = {"128": "Human", "256": "Vehicle", "512": "Animal"}
RECORDING_TYPE_ACTION = "action"
RECORDING_TYPE_MOTION = "on_motion"
RECORDING_TYPE_CONTINUOUS = "continuous"

RECORDING_MODE_LIST = {
    RECORDING_TYPE_MOTION: "M",
    RECORDING_TYPE_CONTINUOUS: "C",
}

SERVER_ID = "server_id"
SERVER_NAME = "server_name"

WEBSOCKET_CHECK_INTERVAL_SECONDS = 120
