"""Unit tests for models and reporting schemas."""

import json
import os
import tempfile
from android_testing_engine.models import TestReport, CrashDetail, DeviceInfo


def test_test_report_schema_compliance():
    """Verifies that all required fields by the BharatSim spec exist in TestReport."""
    required_fields = [
        "test_id",
        "apk_name",
        "package_name",
        "device_name",
        "android_version",
        "installation_status",
        "launch_status",
        "test_duration",
        "crash_detected",
        "crash_details",
        "error_logs",
        "log_file_path",
        "overall_status",
        "timestamp",
    ]

    report = TestReport(
        test_id="test_12345",
        apk_name="sample.apk",
        package_name="com.bharatsim.demo",
        device_name="Redmi 9A",
        android_version="10",
        installation_status="SUCCESS",
        launch_status="SUCCESS",
        test_duration=10.5,
        crash_detected=False,
        crash_details=[],
        error_logs=[],
        log_file_path="/output/logs/test_12345.log",
        overall_status="PASSED"
    )

    data = report.to_dict()
    for field in required_fields:
        assert field in data, f"Required field '{field}' is missing from report dictionary!"

    # Test JSON serialization
    json_str = report.to_json()
    loaded = json.loads(json_str)
    assert loaded["test_id"] == "test_12345"
    assert loaded["overall_status"] == "PASSED"


def test_save_json():
    """Verifies that save_json correctly writes to disk."""
    report = TestReport(
        test_id="test_save",
        apk_name="app.apk",
        package_name="com.test",
        device_name="Pixel 4",
        android_version="12",
        installation_status="SUCCESS",
        launch_status="SUCCESS",
        test_duration=5.0,
        crash_detected=True,
        crash_details=[{"crash_type": "FATAL_EXCEPTION", "reason": "NPE"}],
        error_logs=["Error: NullPointer"],
        overall_status="CRASHED"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = os.path.join(tmpdir, "reports", "report.json")
        saved_path = report.save_json(report_path)
        assert os.path.isfile(saved_path)

        with open(saved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["crash_detected"] is True
            assert data["overall_status"] == "CRASHED"
