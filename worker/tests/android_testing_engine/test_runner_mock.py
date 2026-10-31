"""Unit tests for TestRunner with mocked ADB client."""

import os
import tempfile
import zipfile
from unittest.mock import MagicMock, patch

from android_testing_engine.adb_client import DeviceInfo
from android_testing_engine.runner import TestRunner


def create_dummy_apk(path: str, package: str = "com.test.app"):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("AndroidManifest.xml", package.encode("ascii"))


def test_runner_missing_apk():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = TestRunner(output_dir=tmpdir)
        report = runner.run_test("non_existent.apk")

        assert report.overall_status == "ERROR"
        assert report.installation_status == "FAILED"
        assert "not found" in report.installation_error.lower()
        assert os.path.isfile(report.log_file_path)


def test_runner_no_devices():
    with tempfile.TemporaryDirectory() as tmpdir:
        apk_path = os.path.join(tmpdir, "test.apk")
        create_dummy_apk(apk_path)

        runner = TestRunner(output_dir=tmpdir)
        # Mock ADB available but 0 devices connected
        runner.adb.is_adb_available = MagicMock(return_value=(True, "Android Debug Bridge version 1.0.41"))
        runner.adb.get_connected_devices = MagicMock(return_value=[])

        report = runner.run_test(apk_path)
        assert report.overall_status == "ERROR"
        assert report.installation_status == "SKIPPED"
        assert "no connected android device" in report.installation_error.lower()


def test_runner_successful_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        apk_path = os.path.join(tmpdir, "test.apk")
        create_dummy_apk(apk_path, "com.bharatsim.goodapp")

        runner = TestRunner(output_dir=tmpdir, default_test_duration=0.1)
        runner.adb.is_adb_available = MagicMock(return_value=(True, "ADB ready"))
        runner.adb.get_connected_devices = MagicMock(return_value=[
            DeviceInfo(device_id="emulator-5554", model="Pixel 4", brand="Google", android_version="11", is_emulator=True)
        ])
        runner.adb.clear_logcat = MagicMock()
        runner.adb.install_apk = MagicMock(return_value=(True, "Success"))
        runner.adb.launch_app = MagicMock(return_value=(True, "com.bharatsim.goodapp/.MainActivity", "Success"))
        runner.adb.start_logcat_stream = MagicMock(return_value=None)
        runner.adb.dump_logcat = MagicMock(return_value="10-31 12:00:00.000 I/Test: App started clean\n")

        report = runner.run_test(apk_path, test_duration=0.1)

        assert report.overall_status == "PASSED"
        assert report.installation_status == "SUCCESS"
        assert report.launch_status == "SUCCESS"
        assert report.crash_detected is False
        assert report.package_name == "com.bharatsim.goodapp"
        assert report.device_name == "Google Pixel 4"

        # Verify artifacts
        assert os.path.isfile(report.log_file_path)
        assert os.path.isfile(os.path.join(runner.reports_dir, f"{report.test_id}.json"))
        assert os.path.isfile(os.path.join(runner.reports_dir, "latest_report.json"))


def test_runner_crash_detected():
    with tempfile.TemporaryDirectory() as tmpdir:
        apk_path = os.path.join(tmpdir, "crash_test.apk")
        create_dummy_apk(apk_path, "com.bharatsim.crashapp")

        runner = TestRunner(output_dir=tmpdir, default_test_duration=0.1)
        runner.adb.is_adb_available = MagicMock(return_value=(True, "ADB ready"))
        runner.adb.get_connected_devices = MagicMock(return_value=[
            DeviceInfo(device_id="device-123", model="Redmi 9A", brand="Xiaomi", android_version="10")
        ])
        runner.adb.clear_logcat = MagicMock()
        runner.adb.install_apk = MagicMock(return_value=(True, "Success"))
        runner.adb.launch_app = MagicMock(return_value=(True, "com.bharatsim.crashapp/.MainActivity", "Success"))
        runner.adb.start_logcat_stream = MagicMock(return_value=None)

        crash_log = (
            "10-31 12:00:01.000  1000  1000 E AndroidRuntime: FATAL EXCEPTION: main\n"
            "10-31 12:00:01.000  1000  1000 E AndroidRuntime: Process: com.bharatsim.crashapp, PID: 1000\n"
            "10-31 12:00:01.000  1000  1000 E AndroidRuntime: java.lang.OutOfMemoryError: Failed to allocate memory\n"
            "10-31 12:00:01.000  1000  1000 E AndroidRuntime: \tat com.bharatsim.crashapp.MainActivity.init(MainActivity.java:10)\n"
        )
        runner.adb.dump_logcat = MagicMock(return_value=crash_log)

        report = runner.run_test(apk_path, test_duration=0.1)

        assert report.overall_status == "CRASHED"
        assert report.crash_detected is True
        assert len(report.crash_details) >= 1
        assert "OutOfMemoryError" in report.crash_details[0]["reason"]
