"""This module contains the code to get Camera, NVR and streaming data from a SecuritySpy NVR."""
from __future__ import annotations

import abc
import datetime
import json
import logging
import xmltodict

from typing import Any
from base64 import b64encode

import aiohttp

from .data import (
    SecSpyServerData,
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
    async def async_api_request( self, url: str) -> dict[str, Any]:
        """Override this."""
        raise NotImplementedError(
            "users must define async_api_request to use this base class"
        )

class SecuritySpyAPI(SecuritySpyAPIBase):
    """Default implementation for SecuritySpy api."""

    def __init__(self) -> None:
        """Init the API with or without session."""
        self.session = None

    async def async_api_request(self, url: str) -> dict[str, Any]:
        """Get data from SecuritySpy API."""

        _LOGGER.debug("URL CALLED: %s", url)

        is_new_session = False
        if self.session is None:
            self.session = aiohttp.ClientSession()
            is_new_session = True

        async with self.session.get(url) as response:
            if response.status != 200:
                if is_new_session:
                    await self.session.close()
                raise RequestError(
                    f"Requesting data failed: {response.status} - Reason: {response.reason}"
                )
            data = await response.text()
            if is_new_session:
                await self.session.close()

            json_raw = xmltodict.parse(data)
            json_response = json.loads(json.dumps(json_raw))

            return json_response

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

        if session:
            self._api.session = session

    async def get_server_information(self) -> list[SecSpyServerData]:
        """Return list of Server data."""
        api_url =  f"{self._base_url}/systemInfo?auth={self._token}"
        xml_data = await self._api.async_api_request(api_url)

        return _get_server_information(xml_data)

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
