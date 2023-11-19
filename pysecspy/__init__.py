"""A Python Wrapper for Bensoftware SecuritySpy."""
from __future__ import annotations

from pysecspy.secspy_server import SecSpyServer
from pysecspy.errors import (
    InvalidCredentials,
    RequestError,
    ResultError,
    SecuritySpyError,
)

__title__ = "pysecspy"
__version__ = "2.0.0"
__author__ = "briis"
__license__ = "MIT"
