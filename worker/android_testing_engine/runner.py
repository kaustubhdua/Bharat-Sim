"""
Test Runner module orchestrating the end-to-end Android Testing lifecycle:
Pre-flight checks -> Install -> Detect -> Launch -> Monitor -> Crash Detection -> Report.
"""

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .adb_client import ADBClient, DeviceInfo
from .apk_parser import parse_apk, APKMetadata
from .crash_detector import CrashDetector
from .models import TestReport, CrashDetail


class TestRunner:
    """
    Orchestrates automated testing of an Android APK on an Android device or emulator.
    """
    __test__ = False  # Tell pytest this is an engine class, not a test suite

    def __init__(
        self,
        output_dir: str = "output",
        adb_path: Optional[str] = None,
        default_test_duration: float = 10.0
    ):
        self.output_dir = os.path.abspath(output_dir)
        self.reports_dir = os.path.join(self.output_dir, "reports")
        self.logs_dir = os.path.join(self.output_dir, "logs")
        self.adb = ADBClient(adb_path=adb_path)
        self.default_test_duration = default_test_duration

        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

    def run_test(
        self,
        apk_path: str,
        package_name: Optional[str] = None,
        activity_name: Optional[str] = None,
        device_id: Optional[str] = None,
        test_duration: Optional[float] = None,
        clear_logs_before_test: bool = True,
        uninstall_after_test: bool = False
    ) -> TestReport:
        """
        Executes complete automated test lifecycle for the provided APK.
        Guaranteed to produce a structured TestReport and persist both JSON and log files.
        """
        start_time = time.time()
        test_id = f"test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        apk_name = os.path.basename(apk_path) if apk_path else "unknown.apk"
        duration = test_duration if test_duration is not None else self.default_test_duration
        log_file_path = os.path.join(self.logs_dir, f"{test_id}.log")
        report_file_path = os.path.join(self.reports_dir, f"{test_id}.json")

        report = TestReport(
            test_id=test_id,
            apk_name=apk_name,
            package_name=package_name,
            activity_name=activity_name,
            device_name="None",
            android_version="Unknown",
            installation_status="SKIPPED",
            launch_status="NOT_ATTEMPTED",
            test_duration=0.0,
            crash_detected=False,
            crash_details=[],
            error_logs=[],
            log_file_path=log_file_path,
            overall_status="ERROR",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # 1. Pre-flight Check: Validate APK file
        if not apk_path or not os.path.isfile(apk_path):
            report.installation_error = f"APK file not found: {apk_path}"
            report.error_logs.append(report.installation_error)
            report.installation_status = "FAILED"
            report.overall_status = "ERROR"
            self._finalize_and_save(report, report_file_path, log_file_path, start_time, "")
            return report

        # 2. Extract APK metadata statically (package & launch activity)
        apk_meta: Optional[APKMetadata] = None
        try:
            apk_meta = parse_apk(apk_path)
            if not report.package_name and apk_meta.package_name:
                report.package_name = apk_meta.package_name
            if not report.activity_name and apk_meta.launch_activity:
                report.activity_name = apk_meta.launch_activity
        except Exception as e:
            report.error_logs.append(f"Warning: Static APK parsing encountered issue: {str(e)}")

        # 3. Check ADB installation
        adb_ok, adb_msg = self.adb.is_adb_available()
        if not adb_ok:
            report.installation_error = f"ADB Unavailable: {adb_msg}"
            report.error_logs.append(report.installation_error)
            report.installation_status = "SKIPPED"
            report.overall_status = "ERROR"
            self._finalize_and_save(report, report_file_path, log_file_path, start_time, f"ADB Check Failed: {adb_msg}")
            return report

        # 4. Check connected devices
        try:
            devices = self.adb.get_connected_devices()
        except Exception as e:
            report.installation_error = f"Failed to list ADB devices: {str(e)}"
            report.error_logs.append(report.installation_error)
            report.overall_status = "ERROR"
            self._finalize_and_save(report, report_file_path, log_file_path, start_time, report.installation_error)
            return report

        if not devices:
            report.installation_error = (
                "No connected Android device or emulator found. "
                "Please connect a physical device via USB with USB Debugging enabled, "
                "or start an Android Virtual Device (AVD) emulator."
            )
            report.error_logs.append(report.installation_error)
            report.installation_status = "SKIPPED"
            report.overall_status = "ERROR"
            self._finalize_and_save(report, report_file_path, log_file_path, start_time, report.installation_error)
            return report

        # Select target device
        target_device = None
        if device_id:
            for d in devices:
                if d.device_id == device_id:
                    target_device = d
                    break
            if not target_device:
                report.installation_error = f"Specified device '{device_id}' is not connected or unauthorized."
                report.error_logs.append(report.installation_error)
                report.overall_status = "ERROR"
                self._finalize_and_save(report, report_file_path, log_file_path, start_time, report.installation_error)
                return report
        else:
            # Pick first available device
            target_device = devices[0]

        report.device_id = target_device.device_id
        report.device_name = f"{target_device.brand} {target_device.model}".strip() or target_device.device_id
        report.android_version = target_device.android_version

        # 5. Prepare logging
        if clear_logs_before_test:
            self.adb.clear_logcat(device_id=target_device.device_id)

        # Baseline package list before installation (for auto-detection fallback)
        packages_before = set()
        try:
            packages_before = set(self.adb.get_installed_packages(device_id=target_device.device_id))
        except Exception:
            pass

        # Start live logcat streaming to dedicated log file
        log_process = self.adb.start_logcat_stream(log_file_path, device_id=target_device.device_id)

        # 6. Install APK
        install_success, install_msg = self.adb.install_apk(apk_path, device_id=target_device.device_id)
        if not install_success:
            report.installation_status = "FAILED"
            report.installation_error = install_msg
            report.launch_status = "SKIPPED"
            report.overall_status = "FAILED"
            report.error_logs.append(f"APK Install Error: {install_msg}")
            
            # Stop logcat stream and finalize
            self._stop_log_process(log_process)
            captured_logs = self._read_log_file(log_file_path)
            self._analyze_crashes(report, captured_logs)
            self._finalize_and_save(report, report_file_path, log_file_path, start_time)
            return report

        report.installation_status = "SUCCESS"

        # 7. Package name resolution fallback (if static parser missed it)
        if not report.package_name:
            try:
                packages_after = set(self.adb.get_installed_packages(device_id=target_device.device_id))
                new_packages = packages_after - packages_before
                if new_packages:
                    report.package_name = list(new_packages)[0]
            except Exception:
                pass

        if not report.package_name:
            report.launch_status = "FAILED"
            report.launch_error = "Could not identify package name from APK or device package manager."
            report.error_logs.append(report.launch_error)
            report.overall_status = "FAILED"
            self._stop_log_process(log_process)
            captured_logs = self._read_log_file(log_file_path)
            self._analyze_crashes(report, captured_logs)
            self._finalize_and_save(report, report_file_path, log_file_path, start_time)
            return report

        # 8. Launch Application
        launch_success, launched_act, launch_msg = self.adb.launch_app(
            package_name=report.package_name,
            activity_name=report.activity_name,
            device_id=target_device.device_id
        )

        if launch_success:
            report.launch_status = "SUCCESS"
            if launched_act:
                report.activity_name = launched_act
        else:
            report.launch_status = "FAILED"
            report.launch_error = launch_msg
            report.error_logs.append(f"Launch Error: {launch_msg}")

        # 9. Monitoring Phase: Monitor app execution for the specified duration
        # Sleep for duration while logcat stream captures any runtime fatal exceptions
        time.sleep(max(1.0, duration))

        # 10. Stop log collection and analyze
        self._stop_log_process(log_process)
        
        # Ensure logcat buffer is completely captured
        captured_logs = self._read_log_file(log_file_path)
        if not captured_logs or len(captured_logs.strip()) < 10:
            # If stream capture had issues, pull logcat dump directly
            dump = self.adb.dump_logcat(device_id=target_device.device_id)
            with open(log_file_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(dump)
            captured_logs = dump

        # 11. Run Crash Detection
        self._analyze_crashes(report, captured_logs)

        # 12. Determine Overall Status
        if report.crash_detected:
            report.overall_status = "CRASHED"
        elif report.launch_status == "SUCCESS" and report.installation_status == "SUCCESS":
            report.overall_status = "PASSED"
        else:
            report.overall_status = "FAILED"

        # Optional post-test cleanup
        if uninstall_after_test and report.package_name:
            try:
                self.adb.force_stop(report.package_name, device_id=target_device.device_id)
                self.adb._run_adb(["uninstall", report.package_name], device_id=target_device.device_id)
            except Exception:
                pass

        # 13. Finalize and persist
        self._finalize_and_save(report, report_file_path, log_file_path, start_time)
        return report

    def _analyze_crashes(self, report: TestReport, log_content: str):
        detector = CrashDetector(target_package=report.package_name)
        crash_detected, crash_details, error_logs = detector.analyze_log_content(log_content)

        report.crash_detected = crash_detected
        report.crash_details = [c.to_dict() for c in crash_details]
        
        # Merge error logs uniquely
        existing = set(report.error_logs)
        for err in error_logs:
            if err not in existing:
                report.error_logs.append(err)
                existing.add(err)

    def _stop_log_process(self, process):
        if process:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def _read_log_file(self, file_path: str) -> str:
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    def _finalize_and_save(
        self,
        report: TestReport,
        report_file_path: str,
        log_file_path: str,
        start_time: float,
        fallback_log_text: Optional[str] = None
    ):
        report.test_duration = round(time.time() - start_time, 2)
        report.log_file_path = log_file_path

        # If log file does not exist, write fallback log text
        if not os.path.isfile(log_file_path):
            try:
                with open(log_file_path, "w", encoding="utf-8") as f:
                    f.write(fallback_log_text or "No logs captured.")
            except Exception:
                pass

        # Save structured JSON report
        report.save_json(report_file_path)

        # Also write a symlink/pointer to latest_report.json for backend ease of access
        latest_report_path = os.path.join(self.reports_dir, "latest_report.json")
        try:
            report.save_json(latest_report_path)
        except Exception:
            pass
