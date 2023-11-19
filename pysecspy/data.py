"""Holds the Data Calsses for SecuritySpy Wrapper."""

from __future__ import annotations

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


