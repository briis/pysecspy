"""Constant definitions for SecSpy Wrapper."""

DEVICE_UPDATE_INTERVAL_SECONDS = 60
WEBSOCKET_CHECK_INTERVAL_SECONDS = 120

CAMERA_MESSAGES = ["ARM_C", "DISARM_C", "ARM_M", "DISARM_M", "OFFLINE", "ONLINE"]
EVENT_MESSAGES = ["TRIGGER_M", "FILE"]

RECORDING_TYPE_MOTION = "on_motion"
RECORDING_TYPE_CONTINUOUS = "continuous"
RECORDING_TYPE_OFF = "off"
