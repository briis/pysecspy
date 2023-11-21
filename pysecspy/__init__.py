# ruff: noqa: F401
"""A Python Wrapper for Bensoftware SecuritySpy."""
from __future__ import annotations

from pysecspy.secspy import (
    SecuritySpy,
    InvalidCredentials,
    RequestError,
    ResultError,
)
from pysecspy.data import (
    SecSpyServerData,
)

__title__ = "pysecspy"
__version__ = "2.0.0"
__author__ = "briis"
__license__ = "MIT"
