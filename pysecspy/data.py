"""Holds the Data Calsses for SecuritySpy Wrapper."""

from __future__ import annotations

from typing import Any, Callable

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


