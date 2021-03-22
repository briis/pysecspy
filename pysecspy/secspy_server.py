"""Module to communicate with the SecuritySpy API."""
import logging
import asyncio
import sys
import xml.etree.ElementTree as ET

from typing import Optional
from aiohttp import ClientSession, ClientTimeout
from aiohttp.client_exceptions import ClientError
from base64 import b64encode

_LOGGER = logging.getLogger(__name__)
