#!/usr/bin/env python3
"""Measure real fixture HTTP transfers before/after Android Emulator network shaping."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:4723"
ADB_SERIAL = "emulator-5554"
ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"
PROBE_RE = re.compile(r"HTTP (200|206) · (\d+) ms · (CELLULAR|ETHERNET|WIFI|UNKNOWN|OTHER) · probe (\d+) · bytes (\d+) · attempts (\d+)")


def request(method: str, path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WebDriver HTTP {exc.code} for {path}: {body}") from exc
    if isinstance(result, dict) and isinstance(result.get("value"), dict) and result["value"].get("error"):
        raise RuntimeError(f"WebDriver error: {result['value']}")
    return result


def adb(*args: str, timeout: int = 20) -> str:
    completed = subprocess.run(
        ["adb", "-s", ADB_SERIAL, *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode != 0 or "KO:" in output:
        raise RuntimeError(f"ADB command failed ({' '.join(args)}): {output[-1000:]}")
    return output


def prepare_cellular_transport() -> None:
    """Select the emulator's simulated cellular route once before paired measurements."""
    adb("shell", "svc", "wifi", "disable")
    adb("emu", "gsm", "voice", "home")
    adb("emu", "gsm", "data", "home")
    adb("shell", "svc", "data", "enable")
    # Let the active cellular route and DNS state settle before sampling.
    time.sleep(5)


def speed_limits_bps(speed: str) -> tuple[int, int]:
    """Return expected (upload, download) bits/s for supported emulator speed profiles."""
    presets = {
        "full": (0, 0),
        "umts": (384_000, 384_000),
    }
    if speed in presets:
        return presets[speed]
    parts = speed.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"Invalid emulator speed profile: {speed}")
    return int(parts[0]) * 1000, int(parts[1]) * 1000


def set_network_profile(latency_ms: int | None, speed: str = "full") -> dict:
    """Change only emulator latency/throughput, then require exact console readback."""
    latency = "none" if latency_ms is None else str(latency_ms)
    adb("emu", "network", "delay", latency)
    adb("emu", "network", "speed", speed)
    # Let the emulator network simulator settle after applying a runtime profile.
    # Do not toggle mobile data here: keep the same active transport across samples.
    time.sleep(5)
    upload_bps, download_bps = speed_limits_bps(speed)
    expected = {
        "latency_ms": 0 if latency_ms is None else latency_ms,
        "download_bps": download_bps,
        "upload_bps": upload_bps,
    }
    output = adb("emu", "network", "status")

    def read(pattern: str) -> int:
        match = re.search(pattern, output, re.I)
        if not match:
            raise RuntimeError(f"Could not parse emulator network status: {output}")
        return int(match.group(1))

    observed = {
        "minimum_latency_ms": read(r"minimum latency:\s*(\d+)\s+ms"),
        "maximum_latency_ms": read(r"maximum latency:\s*(\d+)\s+ms"),
        "download_bps": read(r"download speed:\s*(\d+)\s+bits/s"),
        "upload_bps": read(r"upload speed:\s*(\d+)\s+bits/s"),
    }
    expected_latency = 0 if latency_ms is None else latency_ms
    matched = (
        observed["minimum_latency_ms"] == expected_latency
        and observed["maximum_latency_ms"] == expected_latency
        and observed["download_bps"] == expected["download_bps"]
        and observed["upload_bps"] == expected["upload_bps"]
    )
    if not matched:
        raise RuntimeError(f"Network profile readback mismatch: expected={expected}, observed={observed}")
    return {"requested": expected, "observed": observed, "status": "verified"}


def reset_network() -> dict:
    """Restore defaults and verify the emulator network control plane."""
    commands = (
        ("emu", "network", "delay", "none"),
        ("emu", "network", "speed", "full"),
        ("shell", "svc", "wifi", "enable"),
        ("shell", "svc", "data", "enable"),
    )
    command_results = []
    for args in commands:
        completed = subprocess.run(
            ["adb", "-s", ADB_SERIAL, *args],
            capture_output=True, text=True, timeout=20, check=False,
        )
        command_results.append({
            "command": " ".join(args),
            "return_code": completed.returncode,
            "output_tail": (completed.stdout + completed.stderr)[-500:],
        })
    try:
        output = adb("emu", "network", "status")
        def read(pattern: str) -> int | None:
            match = re.search(pattern, output, re.I)
            return int(match.group(1)) if match else None
        observed = {
            "minimum_latency_ms": read(r"minimum latency:\s*(\d+)\s+ms"),
            "maximum_latency_ms": read(r"maximum latency:\s*(\d+)\s+ms"),
            "download_bps": read(r"download speed:\s*(\d+)\s+bits/s"),
            "upload_bps": read(r"upload speed:\s*(\d+)\s+bits/s"),
        }
    except Exception as exc:
        return {"status": "unverified", "command_results": command_results, "error": str(exc)}
    verified = (
        all(item["return_code"] == 0 and "KO:" not in item["output_tail"] for item in command_results)
        and all(value == 0 for value in observed.values())
    )
    return {
        "status": "verified" if verified else "unverified",
        "observed": observed,
        "command_results": command_results,
    }


def wait_for_server() -> None:
    deadline = time.monotonic() + 90
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            request("GET", "/status", timeout=3)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Appium server did not become ready: {last_error}")


def find_element(session: str, using: str, value: str, timeout: int = 25) -> str:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = request("POST", f"/session/{session}/element", {"using": using, "value": value})
            element_id = result.get("value", {}).get(ELEMENT_KEY)
            if element_id:
                return element_id
            last_error = RuntimeError(f"Element response lacked W3C element id: {result}")
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"Could not find element ({using}={value}) within {timeout}s: {last_error}")


def parse_probe_text(text: str) -> dict[str, object] | None:
    """Parse a single fixture UI status line without relying on positional group use at call sites."""
    match = PROBE_RE.fullmatch(text)
    if not match:
        return None
    return {
        "http_status": int(match.group(1)),
        "duration_ms": int(match.group(2)),
        "transport": match.group(3),
        "sequence": int(match.group(4)),
        "bytes_read": int(match.group(5)),
        "attempts": int(match.group(6)),
    }


def wait_for_probe(session: str, element_id: str, after_sequence: int, timeout: int = 160) -> dict:
    deadline = time.monotonic() + timeout
    last_text = ""
    while time.monotonic() < deadline:
        last_text = str(request("GET", f"/session/{session}/element/{element_id}/text", timeout=5).get("value", ""))
        probe = parse_probe_text(last_text)
        if probe and int(probe["sequence"]) > after_sequence:
            if int(probe["bytes_read"]) != 2_000_000:
                raise RuntimeError(f"Fixture downloaded unexpected payload size: {probe['bytes_read']}")
            return probe
        if "probe failed" in last_text.lower() or "returned http" in last_text.lower():
            raise RuntimeError(f"Fixture network probe failed: {last_text}")
        time.sleep(0.5)
    raise RuntimeError(f"Fixture network probe did not complete within {timeout}s: {last_text!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    session_id = None
    phase = "configure_baseline_profile"
    evidence: dict[str, object] = {}
    try:
        phase = "prepare_cellular_transport"
        prepare_cellular_transport()
        phase = "configure_baseline_profile"
        baseline_profile = set_network_profile(None, "full")
        evidence["baseline_profile"] = baseline_profile
        wait_for_server()
        created = request("POST", "/session", {
            "capabilities": {
                "alwaysMatch": {
                    "platformName": "Android",
                    "appium:automationName": "UiAutomator2",
                    "appium:deviceName": ADB_SERIAL,
                    "appium:appPackage": "org.bharatsim.smokeapp",
                    "appium:appActivity": ".MainActivity",
                    "appium:noReset": True,
                    "appium:newCommandTimeout": 120,
                },
                "firstMatch": [{}],
            }
        }, timeout=120)
        value = created.get("value", {})
        session_id = created.get("sessionId") or value.get("sessionId")
        if not session_id:
            raise RuntimeError(f"Appium did not return a session id: {created}")
        base = f"/session/{session_id}"

        action_id = find_element(session_id, "accessibility id", "primary-action")
        status_id = find_element(session_id, "accessibility id", "journey-status")
        probe_id = find_element(session_id, "accessibility id", "network-probe-status")
        status_text = request("GET", base + f"/element/{status_id}/text").get("value")
        if status_text != "Ready":
            raise RuntimeError(f"Fixture did not start in the expected Ready state: {status_text!r}")

        def take_samples(label: str, previous_sequence: int) -> tuple[list[dict], int]:
            samples: list[dict] = []
            evidence["samples_" + label] = samples
            last_sequence = previous_sequence
            for _ in range(3):
                request("POST", base + f"/element/{action_id}/click", {})
                status = request("GET", base + f"/element/{status_id}/text").get("value")
                if status != "Primary action completed":
                    raise RuntimeError(f"Primary action state assertion failed during {label}: {status!r}")
                probe = wait_for_probe(session_id, probe_id, after_sequence=last_sequence)
                if probe["transport"] != "CELLULAR":
                    raise RuntimeError(f"{label} request used unsupported transport: {probe}")
                samples.append(probe)
                last_sequence = probe["sequence"]
            return samples, last_sequence

        # Exclude one cold-start download from all timing comparisons.
        request("POST", base + f"/element/{action_id}/click", {})
        warmup_probe = wait_for_probe(session_id, probe_id, after_sequence=0)
        if warmup_probe["transport"] not in ("CELLULAR", "ETHERNET"):
            raise RuntimeError(f"Warm-up request used unsupported transport: {warmup_probe}")
        last_sequence = warmup_probe["sequence"]

        phase = "baseline_samples"
        baseline_probes, last_sequence = take_samples("baseline", last_sequence)
        evidence["baseline_probes"] = baseline_probes

        # Test bandwidth immediately after baseline to isolate whether the
        # speed control itself affects the next real HTTP transfer. A 5 Mbps
        # cap is below the unbounded baseline but keeps the 2 MB transfer bounded.
        phase = "configure_bandwidth_profile"
        bandwidth_profile = set_network_profile(None, "5000:5000")
        evidence["bandwidth_profile"] = bandwidth_profile
        phase = "bandwidth_samples"
        bandwidth_probes, last_sequence = take_samples("bandwidth-only", last_sequence)
        evidence["bandwidth_probes"] = bandwidth_probes

        # Isolate latency from throughput: full bandwidth, fixed 150 ms delay.
        phase = "configure_latency_profile"
        latency_profile = set_network_profile(150, "full")
        evidence["latency_profile"] = latency_profile
        phase = "latency_samples"
        latency_probes, last_sequence = take_samples("latency-only", last_sequence)
        evidence["latency_probes"] = latency_probes

        baseline_median_ms = statistics.median(p["duration_ms"] for p in baseline_probes)
        latency_median_ms = statistics.median(p["duration_ms"] for p in latency_probes)
        bandwidth_median_ms = statistics.median(p["duration_ms"] for p in bandwidth_probes)
        latency_delta_ms = latency_median_ms - baseline_median_ms
        bandwidth_delta_ms = bandwidth_median_ms - baseline_median_ms
        minimum_latency_delta_ms = 50
        minimum_bandwidth_delta_ms = 500

        if latency_delta_ms < minimum_latency_delta_ms:
            raise RuntimeError(
                "Configured latency was not observed in repeated fixture downloads: "
                f"baseline={baseline_probes}, latency_only={latency_probes}, "
                f"baseline_median_ms={baseline_median_ms}, latency_median_ms={latency_median_ms}, "
                f"delta_ms={latency_delta_ms}, minimum_required_delta_ms={minimum_latency_delta_ms}"
            )
        if bandwidth_delta_ms < minimum_bandwidth_delta_ms:
            raise RuntimeError(
                "Configured bandwidth cap was not observed in repeated fixture downloads: "
                f"baseline={baseline_probes}, bandwidth_only={bandwidth_probes}, "
                f"baseline_median_ms={baseline_median_ms}, bandwidth_median_ms={bandwidth_median_ms}, "
                f"delta_ms={bandwidth_delta_ms}, minimum_required_delta_ms={minimum_bandwidth_delta_ms}"
            )

        phase = "verify_network_reset"
        reset_evidence = reset_network()
        evidence["reset_profile"] = reset_evidence
        if reset_evidence.get("status") != "verified":
            raise RuntimeError(f"Could not verify network profile reset: {reset_evidence}")

        screenshot = request("GET", base + "/screenshot")
        image_data = screenshot.get("value")
        if not isinstance(image_data, str) or not image_data:
            raise RuntimeError("Appium screenshot response was empty")
        screenshot_path = args.artifacts / "appium-primary-action.png"
        screenshot_path.write_bytes(base64.b64decode(image_data, validate=True))

        logcat = subprocess.run(
            ["adb", "-s", ADB_SERIAL, "logcat", "-d", "-t", "2000", "-v", "threadtime"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if logcat.returncode != 0:
            raise RuntimeError(f"Could not collect network-probe logcat evidence: {logcat.stderr[-1000:]}")
        probe_lines = [line for line in logcat.stdout.splitlines() if "BHARATSIM_NETWORK_PROBE" in line]
        if not probe_lines:
            raise RuntimeError("No real network-probe markers were found in emulator logcat")
        observed_ips = set(re.findall(r"endpoint_ip=([0-9.]+)", "\n".join(probe_lines)))
        expected_ip = os.getenv("BHARATSIM_PROBE_IP", "")
        if not expected_ip or observed_ips != {expected_ip}:
            raise RuntimeError(f"Probe endpoint IP evidence mismatch: expected={expected_ip!r}, observed={sorted(observed_ips)}")
        probe_logcat_path = args.artifacts / "appium-network-probe.logcat.txt"
        probe_logcat_path.write_text("\n".join(probe_lines) + "\n", encoding="utf-8")

        report = {
            "status": "passed",
            "package_name": "org.bharatsim.smokeapp",
            "probe_endpoint": os.getenv("BHARATSIM_PROBE_URL", "not-configured"),
            "probe_endpoint_scope": "Public HTTPS transfer from speed.cloudflare.com; the fixture pins the CI-resolved IP while retaining the URL hostname for TLS SNI and certificate verification. The transfer traverses the simulated cellular route. This verifies the fixture path only, not arbitrary uploaded-app traffic.",
            "probe_payload_bytes": 2_000_000,
            "probe_endpoint_ip": expected_ip,
            "probe_logcat": str(probe_logcat_path),
            "assertions": [
                "primary action is located by stable accessibility identifier",
                "tap changes the status text to Primary action completed",
                "each probe downloaded exactly 2,000,000 bytes from the public HTTPS endpoint through the Android Emulator network stack",
                "per-request retry counts are captured in probe evidence",
                "baseline, latency-only, and bandwidth-only probes used the same simulated cellular transport",
                "latency-only median duration exceeded baseline by at least 50 ms",
                "bandwidth-only median duration exceeded baseline by at least 500 ms",
                "emulator network console readback matched each requested profile",
                "emulator network settings were reset and read back at defaults",
            ],
            "baseline_profile": baseline_profile,
            "latency_profile": latency_profile,
            "bandwidth_profile": bandwidth_profile,
            "warmup_probe": warmup_probe,
            "baseline_probes": baseline_probes,
            "latency_probes": latency_probes,
            "bandwidth_probes": bandwidth_probes,
            "baseline_median_ms": baseline_median_ms,
            "latency_median_ms": latency_median_ms,
            "bandwidth_median_ms": bandwidth_median_ms,
            "observed_latency_delta_ms": latency_delta_ms,
            "observed_bandwidth_delta_ms": bandwidth_delta_ms,
            "minimum_required_latency_delta_ms": minimum_latency_delta_ms,
            "minimum_required_bandwidth_delta_ms": minimum_bandwidth_delta_ms,
            "traffic_path_verified": True,
            "reset_profile": reset_evidence,
            "screenshot": str(screenshot_path),
        }
        (args.artifacts / "appium-journey.report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        phase_error = str(exc)
        if session_id:
            try:
                page_source = str(request("GET", f"/session/{session_id}/source").get("value", ""))
                (args.artifacts / "appium-page-source.xml").write_text(page_source)
            except Exception as source_error:
                (args.artifacts / "appium-page-source-error.txt").write_text(str(source_error))
            try:
                image_data = request("GET", f"/session/{session_id}/screenshot").get("value")
                if image_data:
                    (args.artifacts / "appium-failure.png").write_bytes(base64.b64decode(image_data, validate=True))
            except Exception as screenshot_error:
                (args.artifacts / "appium-screenshot-error.txt").write_text(str(screenshot_error))
        logcat_path = args.artifacts / "appium-failure-logcat.txt"
        try:
            logs = subprocess.run(["adb", "-s", ADB_SERIAL, "logcat", "-d", "-t", "2000", "-v", "threadtime"], capture_output=True, text=True, timeout=20, check=False)
            logcat_path.write_text((logs.stdout + "\n" + logs.stderr)[-300000:], encoding="utf-8", errors="replace")
            evidence["failure_logcat_return_code"] = logs.returncode
        except Exception as log_error:
            evidence["failure_logcat_error"] = str(log_error)
        (args.artifacts / "appium-journey.failure.json").write_text(json.dumps({
            "status": "failed", "phase": phase, "error": phase_error,
            "evidence_collected_before_failure": evidence,
            "failure_logcat": str(logcat_path),
        }, indent=2))
        raise
    finally:
        if session_id:
            try:
                request("DELETE", f"/session/{session_id}", timeout=15)
            except Exception as exc:
                print(f"warning: could not close Appium session cleanly: {exc}")
        try:
            reset_after_run = reset_network()
        except Exception as reset_error:
            reset_after_run = {"status": "unverified", "error": str(reset_error)}
        failure_report = args.artifacts / "appium-journey.failure.json"
        if failure_report.exists():
            try:
                saved = json.loads(failure_report.read_text(encoding="utf-8"))
                saved["reset_after_failure"] = reset_after_run
                failure_report.write_text(json.dumps(saved, indent=2), encoding="utf-8")
            except Exception as report_error:
                (args.artifacts / "failure-report-update-error.txt").write_text(str(report_error))


if __name__ == "__main__":
    raise SystemExit(main())
