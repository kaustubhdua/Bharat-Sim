#!/usr/bin/env python3
"""Measure a real fixture HTTP request before/after Android Emulator network shaping."""
from __future__ import annotations

import argparse
import base64
import json
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
PROBE_RE = re.compile(r"HTTP 200 · (\d+) ms · (CELLULAR|ETHERNET|WIFI|UNKNOWN|OTHER) · probe (\d+)")


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


def set_network_profile(latency_ms: int | None) -> dict:
    """Configure the emulator and require exact console readback."""
    # Explicitly register the emulator's simulated cellular service before
    # disabling Wi-Fi; some CI emulator images otherwise report CELLULAR as
    # the active transport but cannot resolve external hosts.
    adb("emu", "gsm", "voice", "home")
    adb("emu", "gsm", "data", "home")
    adb("shell", "svc", "wifi", "disable")
    adb("shell", "svc", "data", "enable")
    if latency_ms is None:
        adb("emu", "network", "delay", "none")
        adb("emu", "network", "speed", "full")
        expected = {"latency_ms": 0, "download_bps": 0, "upload_bps": 0}
    else:
        adb("emu", "network", "delay", str(latency_ms))
        adb("emu", "network", "speed", "3000:12000")
        expected = {"latency_ms": latency_ms, "download_bps": 12000000, "upload_bps": 3000000}
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
    if latency_ms is None:
        matched = (
            observed["minimum_latency_ms"] == 0 and observed["maximum_latency_ms"] == 0
            and observed["download_bps"] == 0 and observed["upload_bps"] == 0
        )
    else:
        matched = (
            observed["minimum_latency_ms"] == latency_ms
            and observed["maximum_latency_ms"] == latency_ms
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


def wait_for_probe(session: str, element_id: str, after_sequence: int, timeout: int = 60) -> dict:
    deadline = time.monotonic() + timeout
    last_text = ""
    while time.monotonic() < deadline:
        last_text = str(request("GET", f"/session/{session}/element/{element_id}/text").get("value", ""))
        match = PROBE_RE.fullmatch(last_text)
        if match and int(match.group(3)) > after_sequence:
            return {"duration_ms": int(match.group(1)), "transport": match.group(2), "sequence": int(match.group(3))}
        if "probe failed" in last_text.lower() or "returned HTTP" in last_text.lower():
            raise RuntimeError(f"Fixture network probe failed: {last_text}")
        time.sleep(0.5)
    raise RuntimeError(f"Fixture network probe did not complete within {timeout}s: {last_text!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    session_id = None
    page_source = ""
    try:
        # Establish an unshaped baseline on cellular before the controlled run.
        baseline_profile = set_network_profile(None)
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

        find_element(session_id, "accessibility id", "fixture-title")
        action_id = find_element(session_id, "accessibility id", "primary-action")
        status_id = find_element(session_id, "accessibility id", "journey-status")
        probe_id = find_element(session_id, "accessibility id", "network-probe-status")

        status_text = request("GET", base + f"/element/{status_id}/text").get("value")
        if status_text != "Ready":
            raise RuntimeError(f"Fixture did not start in the expected Ready state: {status_text!r}")

        # Warm up DNS/TLS once; exclude this cold-start request from timing.
        request("POST", base + f"/element/{action_id}/click", {})
        warmup_probe = wait_for_probe(session_id, probe_id, after_sequence=0)
        if warmup_probe["transport"] not in ("CELLULAR", "ETHERNET"):
            raise RuntimeError(f"Warm-up request used unsupported transport: {warmup_probe}")

        baseline_probes = []
        last_sequence = warmup_probe["sequence"]
        for _ in range(3):
            request("POST", base + f"/element/{action_id}/click", {})
            status_text = request("GET", base + f"/element/{status_id}/text").get("value")
            if status_text != "Primary action completed":
                raise RuntimeError(f"Primary action state assertion failed: {status_text!r}")
            probe = wait_for_probe(session_id, probe_id, after_sequence=last_sequence)
            if probe["transport"] not in ("CELLULAR", "ETHERNET"):
                raise RuntimeError(f"Baseline request used unsupported transport: {probe}")
            baseline_probes.append(probe)
            last_sequence = probe["sequence"]

        # Use repeated requests and compare medians so unrelated jitter in one
        # HTTP request cannot masquerade as a verified network impairment.
        shaped_profile = set_network_profile(150)
        shaped_probes = []
        for _ in range(3):
            request("POST", base + f"/element/{action_id}/click", {})
            probe = wait_for_probe(session_id, probe_id, after_sequence=last_sequence)
            if probe["transport"] not in ("CELLULAR", "ETHERNET"):
                raise RuntimeError(f"Shaped request used unsupported transport: {probe}")
            shaped_probes.append(probe)
            last_sequence = probe["sequence"]

        baseline_median_ms = statistics.median(p["duration_ms"] for p in baseline_probes)
        shaped_median_ms = statistics.median(p["duration_ms"] for p in shaped_probes)
        delta_ms = shaped_median_ms - baseline_median_ms
        # Require a repeatable effect above ordinary timing noise, but do not
        # require the measured HTTP duration delta to equal the emulator console
        # delay exactly: request timing also includes endpoint/network variance.
        # Three-sample medians plus a 50 ms minimum make this an observed effect,
        # not a claim that the full configured delay is visible in app timing.
        minimum_observed_delta_ms = 50
        if delta_ms < minimum_observed_delta_ms:
            raise RuntimeError(
                "Emulator delay was configured but not causally observed in repeated fixture requests: "
                f"baseline={baseline_probes}, shaped={shaped_probes}, "
                f"baseline_median_ms={baseline_median_ms}, shaped_median_ms={shaped_median_ms}, "
                f"delta_ms={delta_ms}, minimum_required_delta_ms={minimum_observed_delta_ms}"
            )

        reset_evidence = reset_network()
        if reset_evidence.get("status") != "verified":
            raise RuntimeError(f"Could not verify network profile reset: {reset_evidence}")

        screenshot = request("GET", base + "/screenshot")
        image_data = screenshot.get("value")
        if not isinstance(image_data, str) or not image_data:
            raise RuntimeError("Appium screenshot response was empty")
        screenshot_path = args.artifacts / "appium-primary-action.png"
        screenshot_path.write_bytes(base64.b64decode(image_data, validate=True))
        report = {
            "status": "passed",
            "package_name": "org.bharatsim.smokeapp",
            "assertions": [
                "fixture title is visible",
                "primary action is located by stable accessibility identifier",
                "tap changes the status text to Primary action completed",
                "baseline and shaped requests return real HTTP 200 responses from https://example.com/",
                "both requests use cellular/Ethernet transport",
                "emulator network console readback matches the configured profile",
                "one cold-start warm-up was excluded, then three baseline and three shaped requests were measured on the same cellular/Ethernet transport",
                "median shaped request is at least 50ms slower than median baseline (minimum signal threshold; not an exact-delay claim)",
            ],
            "baseline_profile": baseline_profile,
            "shaped_profile": shaped_profile,
            "warmup_probe": warmup_probe,
            "baseline_probes": baseline_probes,
            "shaped_probes": shaped_probes,
            "baseline_median_ms": baseline_median_ms,
            "shaped_median_ms": shaped_median_ms,
            "observed_delta_ms": delta_ms,
            "minimum_required_delta_ms": minimum_observed_delta_ms,
            "traffic_path_verified": True,
            "reset_profile": reset_evidence,
            "screenshot": str(screenshot_path),
        }
        (args.artifacts / "appium-journey.report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 0
    except Exception:
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
        raise
    finally:
        if session_id:
            try:
                request("DELETE", f"/session/{session_id}", timeout=15)
            except Exception as exc:
                print(f"warning: could not close Appium session cleanly: {exc}")
        reset_network()


if __name__ == "__main__":
    raise SystemExit(main())
