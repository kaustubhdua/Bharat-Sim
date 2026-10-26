#!/usr/bin/env python3
"""Bounded local APK smoke runner for a disposable Android test device.

This script is deliberately not invoked by the API. Set an explicit opt-in flag
and device serial before executing an authorized APK in an isolated environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_cmd(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def valid_package_name(value: str) -> bool:
    """Allow ordinary Java-style package identifiers only; reject shell syntax."""
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+", value))




def parse_emulator_network_status(output: str) -> dict[str, int] | None:
    """Parse the Android Emulator console's network status response."""
    patterns = {
        "download_bps": r"download speed:\s*(\d+)\s+bits/s",
        "upload_bps": r"upload speed:\s*(\d+)\s+bits/s",
        "minimum_latency_ms": r"minimum latency:\s*(\d+)\s+ms",
        "maximum_latency_ms": r"maximum latency:\s*(\d+)\s+ms",
    }
    values: dict[str, int] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, output, re.I)
        if not match:
            return None
        values[key] = int(match.group(1))
    return values


def apply_emulator_network_profile(
    serial: str, latency_ms: int, down_kbps: int, up_kbps: int, packet_loss_pct: float
) -> dict[str, object]:
    """Apply and read back emulator console controls; never claim packet loss or app-path proof."""
    evidence: dict[str, object] = {
        "requested": {
            "latency_ms": latency_ms, "download_kbps": down_kbps,
            "upload_kbps": up_kbps, "packet_loss_pct": packet_loss_pct,
        },
        "supported_controls": ["network_latency", "download_bandwidth", "upload_bandwidth"],
        "unsupported_controls": ["cpu_pressure", "ram_pressure", "storage_pressure", "battery_saver"]
        + (["packet_loss"] if packet_loss_pct > 0 else []),
        "traffic_path_verified": False,
        "note": (
            "Emulator console status verifies the emulator control plane only; it does not prove "
            "the app's active network interface traversed these controls."
        ),
    }
    if not re.fullmatch(r"emulator-\d+", serial):
        evidence.update({"control_plane": {"status": "unsupported", "reason": "Target is not an Android Emulator serial"}})
        return evidence

    commands = [
        ("delay", ["adb", "-s", serial, "emu", "network", "delay", str(latency_ms), str(latency_ms if latency_ms else 0)]),
        ("speed", ["adb", "-s", serial, "emu", "network", "speed", str(up_kbps), str(down_kbps)]),
    ]
    command_evidence: dict[str, object] = {}
    for name, command in commands:
        result = run_cmd(command, timeout=15)
        command_evidence[name] = {
            "return_code": result.returncode,
            "stdout": result.stdout[-1000:],
            "stderr": result.stderr[-1000:],
        }

    status_result = run_cmd(["adb", "-s", serial, "emu", "network", "status"], timeout=15)
    status = parse_emulator_network_status(status_result.stdout + "\n" + status_result.stderr)
    expected = {
        "download_bps": down_kbps * 1000,
        "upload_bps": up_kbps * 1000,
        "minimum_latency_ms": latency_ms,
        "maximum_latency_ms": latency_ms,
    }
    matched = bool(status) and all(status.get(key) == value for key, value in expected.items())
    commands_ok = all(
        isinstance(item, dict) and item.get("return_code") == 0
        and "KO:" not in str(item.get("stdout", "") + item.get("stderr", ""))
        for item in command_evidence.values()
    )
    verified = bool(matched and commands_ok and status_result.returncode == 0)
    evidence["control_plane"] = {
        "status": "verified" if verified else "unverified",
        "commands": command_evidence,
        "readback": status,
        "expected_readback": expected,
        "status_command_return_code": status_result.returncode,
        "status_command_output": (status_result.stdout + "\n" + status_result.stderr)[-2000:],
    }
    evidence["network_constraints_applied"] = verified
    return evidence


def reset_emulator_network_profile(serial: str) -> dict[str, object]:
    """Restore the disposable emulator's default network settings after a run."""
    if not re.fullmatch(r"emulator-\d+", serial):
        return {"status": "not_applicable", "reason": "Target is not an Android Emulator serial"}
    delay = run_cmd(["adb", "-s", serial, "emu", "network", "delay", "none"], timeout=15)
    speed = run_cmd(["adb", "-s", serial, "emu", "network", "speed", "full"], timeout=15)
    status_result = run_cmd(["adb", "-s", serial, "emu", "network", "status"], timeout=15)
    status = parse_emulator_network_status(status_result.stdout + "\n" + status_result.stderr)
    restored = (
        delay.returncode == 0 and speed.returncode == 0 and status_result.returncode == 0
        and bool(status)
        and status.get("minimum_latency_ms") == 0
        and status.get("maximum_latency_ms") == 0
        and status.get("download_bps") == 0
        and status.get("upload_bps") == 0
    )
    return {
        "status": "verified" if restored else "unverified",
        "readback": status,
        "commands_return_codes": [delay.returncode, speed.returncode, status_result.returncode],
    }

\ndef main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--duration", type=int, default=20, help="seconds to observe the launched app (1–120)")
    parser.add_argument("--out", type=Path, default=Path("artifacts"))
    args = parser.parse_args()

    if os.getenv("BHARATSIM_ENABLE_LOCAL_APK_EXECUTION") != "true":
        parser.error("refusing to execute APK: set BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true after isolating the worker")
    serial = os.getenv("ANDROID_SERIAL", "").strip()
    if not serial:
        parser.error("ANDROID_SERIAL must explicitly identify the disposable test device")
    if not 1 <= args.duration <= 120:
        parser.error("--duration must be between 1 and 120 seconds")
    apk = args.apk.resolve()
    if not apk.is_file() or apk.suffix.lower() != ".apk":
        parser.error("APK path must be an existing .apk file")
    if apk.stat().st_size > 150 * 1024 * 1024:
        parser.error("APK exceeds 150 MiB limit")
    if shutil.which("adb") is None or shutil.which("aapt") is None:
        parser.error("adb and aapt must both be available on PATH")
    with apk.open("rb") as stream:
        if stream.read(4)[:2] != b"PK":
            parser.error("APK does not have a ZIP archive signature")
    try:
        with zipfile.ZipFile(apk) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > 10000:
                parser.error("APK archive has an invalid or excessive entry count")
            if "AndroidManifest.xml" not in {entry.filename for entry in entries}:
                parser.error("APK archive is missing AndroidManifest.xml")
            uncompressed = 0
            for entry in entries:
                if entry.flag_bits & 0x1:
                    parser.error("Encrypted archive entries are not accepted")
                uncompressed += entry.file_size
                if uncompressed > 1024 * 1024 * 1024:
                    parser.error("APK expands beyond the 1 GiB metadata limit")
                if entry.file_size and (entry.compress_size == 0 or entry.file_size / entry.compress_size > 1000):
                    parser.error("APK contains a suspicious compression ratio")
    except zipfile.BadZipFile:
        parser.error("APK is not a valid ZIP archive")

    started = now()
    hasher = hashlib.sha256()
    with apk.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    report: dict[str, object] = {
        "schema_version": "1.0",
        "started_at": started,
        "apk_name": apk.name,
        "apk_sha256": digest,
        "device_serial": serial,
        "status": "failed",
        "steps": [],
        "limitations": [
            "Smoke test only; no app-specific interaction flow is automated.",
            "Network shaping, memory pressure and storage pressure are not applied by this script.",
            "A missing crash marker does not prove the app is healthy.",
        ],
    }
    steps: list[dict[str, object]] = report["steps"]  # type: ignore[assignment]

    def record(name: str, result: subprocess.CompletedProcess[str], duration: float) -> None:
        steps.append({
            "name": name, "return_code": result.returncode, "duration_seconds": round(duration, 3),
            "stdout_tail": result.stdout[-3000:], "stderr_tail": result.stderr[-3000:],
        })

    try:
        t = time.monotonic()
        devices = run_cmd(["adb", "-s", serial, "get-state"], timeout=8)
        record("device_preflight", devices, time.monotonic() - t)
        if devices.returncode != 0 or devices.stdout.strip() != "device":
            raise RuntimeError("selected ADB device is not online")

        t = time.monotonic()
        badging = run_cmd(["aapt", "dump", "badging", str(apk)], timeout=15)
        record("read_package_metadata", badging, time.monotonic() - t)
        match = re.search(r"^package: name='([^']+)'", badging.stdout, re.M)
        if badging.returncode != 0 or not match:
            raise RuntimeError("could not read package name from APK using aapt")
        package_name = match.group(1)
        # The package name is later passed to an adb shell command. Validate it
        # strictly to prevent APK-controlled shell metacharacters reaching the device.
        if not valid_package_name(package_name):
            raise RuntimeError("APK contains an invalid Android package name")
        report["package_name"] = package_name

        t = time.monotonic()
        clear = run_cmd(["adb", "-s", serial, "logcat", "-c"], timeout=10)
        record("clear_logcat", clear, time.monotonic() - t)
        if clear.returncode != 0:
            raise RuntimeError("could not clear logcat before run")

        t = time.monotonic()
        install = run_cmd(["adb", "-s", serial, "install", "-r", str(apk)], timeout=90)
        record("install_apk", install, time.monotonic() - t)
        if install.returncode != 0 or "Success" not in install.stdout:
            raise RuntimeError("APK installation failed")

        t = time.monotonic()
        launch = run_cmd(["adb", "-s", serial, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"], timeout=20)
        record("launch_app", launch, time.monotonic() - t)
        if launch.returncode != 0 or "No activities found" in launch.stdout + launch.stderr:
            raise RuntimeError("could not launch app using launcher intent")

        time.sleep(args.duration)
        t = time.monotonic()
        logs = run_cmd(["adb", "-s", serial, "logcat", "-d", "-t", "5000", "-v", "threadtime"], timeout=30)
        record("collect_logcat", logs, time.monotonic() - t)
        if logs.returncode != 0:
            raise RuntimeError("logcat collection failed")
        args.out.mkdir(parents=True, exist_ok=True)
        stem = digest[:12]
        log_path = args.out / (stem + ".logcat.txt")
        log_path.write_text(logs.stdout, encoding="utf-8", errors="replace")
        report["logcat_artifact"] = str(log_path)
        report["logcat_bytes"] = len(logs.stdout.encode("utf-8", errors="replace"))
        report["fatal_exception_marker"] = bool(re.search(r"FATAL EXCEPTION|Fatal signal|SIGSEGV", logs.stdout, re.I))
        if report["fatal_exception_marker"]:
            report["status"] = "failed"
            report["error"] = "Fatal crash marker observed during the smoke-test observation window"
        else:
            report["status"] = "completed"
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        report["error"] = str(exc)
    # Always attempt to remove the test package from a reusable disposable
    # emulator. This is cleanup, not a substitute for reverting a VM snapshot.
    if report.get("package_name"):
        t = time.monotonic()
        uninstall = run_cmd(["adb", "-s", serial, "uninstall", str(report["package_name"])], timeout=30)
        record("cleanup_uninstall", uninstall, time.monotonic() - t)
        if uninstall.returncode != 0 and "Unknown package" not in (uninstall.stdout + uninstall.stderr):
            report["cleanup_warning"] = "Could not uninstall the test package; reset or discard this emulator before another job."
            if report["status"] == "completed":
                report["status"] = "failed"
                report["error"] = report["cleanup_warning"]
    report["finished_at"] = now()
    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / (digest[:12] + ".report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(report_path), "apk_sha256": digest, "package_name": report.get("package_name"), "error": report.get("error")}, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
