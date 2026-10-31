"""
BharatSim Android Testing Engine
Module for automated Android application installation, launch testing,
crash/ANR detection, log collection, and structured reporting.
"""

from .models import TestReport, CrashDetail, DeviceInfo
from .adb_client import ADBClient, ADBError
from .apk_parser import parse_apk, APKMetadata
from .crash_detector import CrashDetector
from .runner import TestRunner
from .cli import main

__all__ = [
    "TestRunner",
    "TestReport",
    "CrashDetail",
    "DeviceInfo",
    "ADBClient",
    "ADBError",
    "parse_apk",
    "APKMetadata",
    "CrashDetector",
    "main",
]

__version__ = "1.0.0"
