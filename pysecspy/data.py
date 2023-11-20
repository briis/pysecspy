"""Holds the Data Calsses for SecuritySpy Wrapper."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable

MAX_SUPPORTED_CAMERAS = 256
MAX_EVENT_HISTORY_IN_STATE_MACHINE = MAX_SUPPORTED_CAMERAS * 2

class SecSpyDevice:
    """SecuritySpy camera device."""

    def __init__(
        self,
        name: str,
        model: str,
        online: bool,
        enabled: bool,
        recordingmode_a: str,
        recordingmode_c: str,
        recordingmode_m: str,
        ip_address: str,
        livestream_url: str,
        latestimage_url: str,
        image_width: int,
        image_height: int,
        fps: int,
        video_format: str,
        ptz_features: str,
        ptz_presets: object,
    ) -> None:
        """Initialize camera device."""
        self._name = name
        self._model = model
        self._online = online
        self._enabled = enabled
        self._recordingmode_a = recordingmode_a
        self._recordingmode_c = recordingmode_c
        self._recordingmode_m = recordingmode_m
        self._ip_address = ip_address
        self._livestream_url = livestream_url
        self._latestimage_url = latestimage_url
        self._image_width = image_width
        self._image_height = image_height
        self._fps = fps
        self._video_format = video_format
        self._ptz_features = ptz_features
        self._ptz_presets = ptz_presets


class SecSpyServerData:
    """Class to hold server information."""

    # pylint: disable=R0913, R0902, R0914
    def __init__(
            self,
            ip_address: str,
            name: str,
            port: int,
            presets: object,
            uuid: str,
            version: str,
    ) -> None:
        """Dataset constructor."""
        self._ip_address = ip_address
        self._name = name
        self._port = port
        self._presets = presets
        self._uuid = uuid
        self._version = version

    @property
    def ip_address(self) -> str:
        """IP Adress of Server."""
        return self._ip_address

    @property
    def name(self) -> str:
        """Name of Server."""
        return self._name

    @property
    def port(self) -> int:
        """Port of Server."""
        return self._port

    @property
    def presets(self) -> object:
        """Presets defined on Server."""
        return self._presets

    @property
    def uuid(self) -> str:
        """Unique Id of Server."""
        return self._uuid

    @property
    def version(self) -> str:
        """SW Version for Server."""
        return self._version



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