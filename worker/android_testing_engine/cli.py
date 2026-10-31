"""
Command Line Interface (CLI) for BharatSim Android Testing Engine.
Provides commands for running APK tests, listing connected devices,
checking ADB availability, and inspecting APK metadata.
"""

import argparse
import json
import os
import sys
from typing import List, Optional

from .adb_client import ADBClient
from .apk_parser import parse_apk
from .runner import TestRunner


def format_status(status: str) -> str:
    """Formats status with simple ASCII tags for Windows compatibility."""
    status_upper = status.upper()
    if status_upper in ("PASSED", "SUCCESS"):
        return f"[PASSED] {status}"
    elif status_upper in ("CRASHED", "FAILED"):
        return f"[FAILED] {status}"
    elif status_upper in ("SKIPPED", "NOT_ATTEMPTED"):
        return f"[SKIPPED] {status}"
    return f"[{status_upper}]"


def cmd_check_adb(args: argparse.Namespace) -> int:
    """Checks ADB availability and outputs status."""
    print("Checking Android Debug Bridge (ADB)...")
    client = ADBClient(adb_path=args.adb_path)
    ok, msg = client.is_adb_available()
    if ok:
        print(f"[OK] ADB is installed and accessible: {msg}")
        if client.adb_bin:
            print(f"     Binary Path: {client.adb_bin}")
        return 0
    else:
        print(f"[ERROR] {msg}")
        return 1


def cmd_list_devices(args: argparse.Namespace) -> int:
    """Lists all connected Android devices and emulators."""
    client = ADBClient(adb_path=args.adb_path)
    ok, msg = client.is_adb_available()
    if not ok:
        print(f"[ERROR] ADB is unavailable: {msg}")
        return 1

    devices = client.get_connected_devices()
    print(f"\nConnected Android Devices ({len(devices)} found):")
    print("-" * 65)
    if not devices:
        print("  No devices/emulators connected or authorized.")
        print("  Connect a device via USB with USB debugging enabled,")
        print("  or start an Android emulator (AVD).")
        return 0

    for idx, dev in enumerate(devices, 1):
        dev_type = "Emulator" if dev.is_emulator else "Physical Device"
        print(f"  {idx}. ID: {dev.device_id}")
        print(f"     Model:       {dev.brand} {dev.model}")
        print(f"     Android OS:  {dev.android_version} (API {dev.api_level})")
        print(f"     Type:        {dev_type}")
        print("-" * 65)
    return 0


def cmd_parse_apk(args: argparse.Namespace) -> int:
    """Inspects and parses APK metadata without requiring a connected device."""
    if not os.path.isfile(args.apk_path):
        print(f"[ERROR] File not found: {args.apk_path}")
        return 1

    print(f"Inspecting APK: {args.apk_path}")
    try:
        meta = parse_apk(args.apk_path)
        print("\nAPK Metadata:")
        print(f"  Package Name:    {meta.package_name or 'Not detected'}")
        print(f"  Launch Activity: {meta.launch_activity or 'Not detected'}")
        print(f"  Version Code:    {meta.version_code or 'Unknown'}")
        print(f"  Version Name:    {meta.version_name or 'Unknown'}")
        print(f"  App Label:       {meta.app_label or 'Unknown'}")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to parse APK: {str(e)}")
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Executes the full automated testing engine on an APK."""
    print("=" * 65)
    print(" BharatSim - Android Testing Engine (Person 2)")
    print(" HackFront India 2026 - T1.2 The Cheap Phone Test")
    print("=" * 65)
    print(f"Target APK:        {args.apk_path}")
    print(f"Test Duration:     {args.duration}s")
    print(f"Output Directory:  {os.path.abspath(args.output)}")
    if args.device:
        print(f"Target Device:     {args.device}")
    print("-" * 65)

    runner = TestRunner(
        output_dir=args.output,
        adb_path=args.adb_path,
        default_test_duration=args.duration
    )

    report = runner.run_test(
        apk_path=args.apk_path,
        package_name=args.package,
        activity_name=args.activity,
        device_id=args.device,
        test_duration=args.duration,
        clear_logs_before_test=not args.no_clear_logs,
        uninstall_after_test=args.uninstall
    )

    # Console Summary
    print("\n" + "=" * 65)
    print(" TEST EXECUTION SUMMARY")
    print("=" * 65)
    print(f"  Test ID:             {report.test_id}")
    print(f"  APK Name:            {report.apk_name}")
    print(f"  Package Name:        {report.package_name or 'N/A'}")
    print(f"  Device:              {report.device_name} (Android {report.android_version})")
    print(f"  Installation Status: {report.installation_status}")
    print(f"  Launch Status:       {report.launch_status}")
    print(f"  Test Duration:       {report.test_duration}s")
    print(f"  Crash Detected:      {'YES - [CRITICAL]' if report.crash_detected else 'NO'}")
    print(f"  Overall Status:      {format_status(report.overall_status)}")
    print("-" * 65)

    if report.crash_detected:
        print("\n[!] DETECTED CRASH DETAILS:")
        for idx, crash in enumerate(report.crash_details, 1):
            print(f"  Crash #{idx} [{crash.get('crash_type')}]:")
            print(f"    Reason:    {crash.get('reason')}")
            print(f"    Timestamp: {crash.get('timestamp')}")
            if crash.get("pid"):
                print(f"    PID:       {crash.get('pid')}")
            trace = crash.get("stack_trace", [])
            if trace:
                print("    Stack Trace (first 5 lines):")
                for line in trace[:5]:
                    print(f"      {line}")

    if report.error_logs:
        print(f"\n[i] Key Error/Logcat Highlights ({min(5, len(report.error_logs))} shown):")
        for err in report.error_logs[:5]:
            print(f"    - {err}")

    report_path = os.path.join(runner.reports_dir, f"{report.test_id}.json")
    print("\nArtifacts Saved:")
    print(f"  - Structured JSON Report: {report_path}")
    print(f"  - Device Logcat Log:      {report.log_file_path}")
    print(f"  - Latest Report Link:     {os.path.join(runner.reports_dir, 'latest_report.json')}")
    print("=" * 65)

    return 0 if report.overall_status == "PASSED" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bharatsim-test",
        description="BharatSim Android Testing Engine - Automated APK Installation, Launch, & Crash Detection"
    )
    parser.add_argument("--adb-path", default=None, help="Custom path to adb binary")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run automated test on an APK")
    run_parser.add_argument("apk_path", help="Path to the Android APK file to test")
    run_parser.add_argument("--package", default=None, help="Explicit package name (bypasses auto-detection)")
    run_parser.add_argument("--activity", default=None, help="Explicit main activity (bypasses auto-detection)")
    run_parser.add_argument("--device", default=None, help="Target device serial ID (if multiple devices)")
    run_parser.add_argument("--duration", type=float, default=10.0, help="Monitoring duration in seconds (default: 10.0)")
    run_parser.add_argument("--output", default="output", help="Directory to save reports and logs (default: output)")
    run_parser.add_argument("--uninstall", action="store_true", help="Uninstall application after testing completes")
    run_parser.add_argument("--no-clear-logs", action="store_true", help="Do not clear logcat buffer prior to test")

    # Command: devices
    subparsers.add_parser("devices", help="List connected Android devices and emulators")

    # Command: check-adb
    subparsers.add_parser("check-adb", help="Verify ADB binary accessibility and version")

    # Command: parse-apk
    parse_parser = subparsers.add_parser("parse-apk", help="Inspect APK metadata without a connected device")
    parse_parser.add_argument("apk_path", help="Path to APK file to inspect")

    # Command: self-test (Offline mode)
    self_test_parser = subparsers.add_parser(
        "self-test",
        help="Run minimal offline self-test using synthetic data (No phone or APK required, clearly labelled as SIMULATED)"
    )
    self_test_parser.add_argument("--output", default="output", help="Directory to save reports and logs (default: output)")
    self_test_parser.add_argument("--simulate-crash", action="store_true", help="Simulate a crash event in the offline test")

    return parser


def cmd_self_test(args: argparse.Namespace) -> int:
    """
    Executes a minimal offline self-test using synthetic data.
    Generates a full structured TestReport and logcat file, clearly labelled as SIMULATED.
    """
    from datetime import datetime, timezone
    from .crash_detector import CrashDetector
    from .models import TestReport

    print("=" * 65)
    print(" BharatSim - Android Testing Engine (Offline Self-Test)")
    print(" Status: [SIMULATED MODE - NO PHYSICAL DEVICE/APK REQUIRED]")
    print("=" * 65)

    test_id = f"test_simulated_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    reports_dir = os.path.join(args.output, "reports")
    logs_dir = os.path.join(args.output, "logs")
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    log_file_path = os.path.join(logs_dir, f"{test_id}.log")
    report_file_path = os.path.join(reports_dir, f"{test_id}.json")
    package_name = "com.bharatsim.simulated.testapp"

    # Generate synthetic logcat stream
    if args.simulate_crash:
        simulated_log = (
            "10-31 12:00:00.100  1000  1000 I ActivityManager: Start proc 1500:com.bharatsim.simulated.testapp/u0a100 for activity\n"
            "10-31 12:00:00.500  1500  1500 D BharatSim: Initializing simulated test app components\n"
            "10-31 12:00:01.000  1500  1500 E AndroidRuntime: FATAL EXCEPTION: main\n"
            "10-31 12:00:01.000  1500  1500 E AndroidRuntime: Process: com.bharatsim.simulated.testapp, PID: 1500\n"
            "10-31 12:00:01.000  1500  1500 E AndroidRuntime: java.lang.NullPointerException: Attempt to invoke virtual method on a null object reference\n"
            "10-31 12:00:01.000  1500  1500 E AndroidRuntime: \tat com.bharatsim.simulated.testapp.MainActivity.onCreate(MainActivity.java:24)\n"
            "10-31 12:00:01.010  1000  1200 I ActivityManager: Process com.bharatsim.simulated.testapp (pid 1500) has died\n"
        )
    else:
        simulated_log = (
            "10-31 12:00:00.100  1000  1000 I ActivityManager: Start proc 1500:com.bharatsim.simulated.testapp/u0a100 for activity\n"
            "10-31 12:00:00.300  1500  1500 D BharatSim: Initializing simulated test app components\n"
            "10-31 12:00:00.600  1500  1500 I BharatSim: MainActivity successfully rendered frame\n"
            "10-31 12:00:01.000  1500  1500 D BharatSim: Application running in stable state (T1.2 Benchmark)\n"
        )

    # Write synthetic log file
    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write(simulated_log)

    # Analyze synthetic logs using actual CrashDetector
    detector = CrashDetector(target_package=package_name)
    crash_detected, crash_details, error_logs = detector.analyze_log_content(simulated_log)

    overall_status = "CRASHED" if crash_detected else "PASSED"

    report = TestReport(
        test_id=test_id,
        apk_name="SIMULATED_synthetic_test.apk",
        package_name=package_name,
        device_name="SIMULATED Generic Android Device (Offline Test)",
        android_version="10 (Go Edition)",
        installation_status="SUCCESS",
        launch_status="SUCCESS",
        test_duration=1.5,
        crash_detected=crash_detected,
        crash_details=[c.to_dict() for c in crash_details],
        error_logs=error_logs,
        log_file_path=os.path.abspath(log_file_path),
        overall_status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        device_id="SIMULATED-EMU-001",
        activity_name=f"{package_name}/.MainActivity"
    )

    report.save_json(report_file_path)
    latest_report_path = os.path.join(reports_dir, "latest_report.json")
    report.save_json(latest_report_path)

    print("\n" + "=" * 65)
    print(" TEST EXECUTION SUMMARY [SIMULATED]")
    print("=" * 65)
    print(f"  Test ID:             {report.test_id}")
    print(f"  APK Name:            {report.apk_name}")
    print(f"  Package Name:        {report.package_name}")
    print(f"  Device:              {report.device_name} (Android {report.android_version})")
    print(f"  Installation Status: {report.installation_status}")
    print(f"  Launch Status:       {report.launch_status}")
    print(f"  Test Duration:       {report.test_duration}s")
    print(f"  Crash Detected:      {'YES - [SIMULATED CRASH]' if report.crash_detected else 'NO'}")
    print(f"  Overall Status:      {format_status(report.overall_status)}")
    print("-" * 65)
    print("Artifacts Saved:")
    print(f"  - Structured JSON Report: {os.path.abspath(report_file_path)}")
    print(f"  - Device Logcat Log:      {os.path.abspath(log_file_path)}")
    print(f"  - Latest Report Link:     {os.path.abspath(latest_report_path)}")
    print("=" * 65)

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "devices":
        return cmd_list_devices(args)
    elif args.command == "check-adb":
        return cmd_check_adb(args)
    elif args.command == "parse-apk":
        return cmd_parse_apk(args)
    elif args.command == "self-test":
        return cmd_self_test(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
