"""
Data models and schemas for BharatSim Android Testing Engine.
Designed for clean integration with Person 5 (Backend / API).
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import json
import os
from datetime import datetime, timezone


@dataclass
class CrashDetail:
    """Detailed record of a single detected crash or fatal exception."""
    crash_type: str  # e.g., "FATAL_EXCEPTION", "NATIVE_CRASH", "ANR", "PROCESS_DIED"
    reason: str  # e.g. "java.lang.NullPointerException: Attempt to invoke..."
    timestamp: str  # ISO timestamp or logcat timestamp
    pid: Optional[str] = None
    process_name: Optional[str] = None
    stack_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceInfo:
    """Information about the target Android device / emulator."""
    device_id: str
    model: str = "Unknown"
    manufacturer: str = "Unknown"
    brand: str = "Unknown"
    android_version: str = "Unknown"
    api_level: str = "Unknown"
    is_emulator: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestReport:
    """
    Structured test execution report.
    Directly conforms to BharatSim Person 2 specification and Person 5 ingestion requirements.
    """
    __test__ = False  # Tell pytest this is a data model, not a test suite

    test_id: str
    apk_name: str
    package_name: Optional[str]
    device_name: str
    android_version: str
    installation_status: str  # SUCCESS, FAILED, SKIPPED
    launch_status: str        # SUCCESS, FAILED, SKIPPED, NOT_ATTEMPTED
    test_duration: float      # in seconds
    crash_detected: bool
    crash_details: List[Dict[str, Any]] = field(default_factory=list)
    error_logs: List[str] = field(default_factory=list)
    log_file_path: Optional[str] = None
    overall_status: str = "ERROR"  # PASSED, FAILED, CRASHED, ERROR
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Extra metadata useful for backend and cheap phone analysis
    device_id: Optional[str] = None
    activity_name: Optional[str] = None
    installation_error: Optional[str] = None
    launch_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save_json(self, destination_path: str) -> str:
        """Saves report to disk, creating parent directories if needed."""
        abs_path = os.path.abspath(destination_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(self.to_json(indent=2))
        return abs_path
