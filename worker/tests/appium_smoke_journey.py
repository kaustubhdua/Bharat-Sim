#!/usr/bin/env python3
"""Verify fixture HTTPS traffic through an allowlisted, shaped CONNECT proxy."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import statistics
import subprocess
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

BASE = "http://127.0.0.1:4723"
PROXY_CONTROL = "http://127.0.0.1:8889"
ADB_SERIAL = "emulator-5554"
PROBE_BYTES = 64_000
ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"
PROBE_RE = re.compile(r"HTTP (200|206) · (\d+) ms · (CELLULAR|ETHERNET|WIFI|UNKNOWN|OTHER) · probe (\d+) · bytes (\d+) · attempts (\d+)")
EXPECTED_URL = os.getenv("BHARATSIM_PROBE_URL", "")
EXPECTED_HOST = urlsplit(EXPECTED_URL).hostname or ""
EXPECTED_IP = os.getenv("BHARATSIM_PROBE_IP", "")


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


def proxy_request(method: str, path: str, payload: dict | None = None, timeout: int = 5) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        PROXY_CONTROL + path,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Proxy control HTTP {exc.code} for {path}: {body}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"Proxy control returned a non-object for {path}")
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


def has_active_network(connectivity: str) -> bool:
    return bool(re.search(r"(?:WiFi|Cellular|Ethernet) active networks:\s*\{[^}]+\}", connectivity, re.I))


def prepare_proxy_path() -> dict:
    """Keep a real Android network active and verify the host CONNECT proxy is ready."""
    adb("shell", "settings", "put", "global", "airplane_mode_on", "0")
    adb("shell", "cmd", "connectivity", "airplane-mode", "disable")
    adb("shell", "svc", "wifi", "enable")
    adb("shell", "svc", "data", "enable")
    last_connectivity = ""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        last_connectivity = adb("shell", "dumpsys", "connectivity", timeout=8)
        if has_active_network(last_connectivity):
            health = proxy_request("GET", "/health")
            if health.get("status") != "ok":
                raise RuntimeError(f"HTTPS shaping proxy is not healthy: {health}")
            return {
                "status": "ready",
                "active_transport_network_present": True,
                "connectivity_tail": last_connectivity[-1800:],
                "proxy_health": health,
            }
        time.sleep(1)
    raise RuntimeError(
        "Android emulator has no active network for the CONNECT proxy path; "
        f"connectivity={last_connectivity[-4000:]!r}"
    )


def set_proxy_profile(label: str, delay_ms: int, rate_kbps: int) -> dict:
    result = proxy_request("POST", "/config", {
        "label": label,
        "delay_ms": delay_ms,
        "rate_kbps": rate_kbps,
    })
    config = result.get("config")
    if result.get("status") != "ok" or not isinstance(config, dict):
        raise RuntimeError(f"Proxy profile configuration failed: {result}")
    expected = {"label": label, "delay_ms": delay_ms, "rate_kbps": rate_kbps}
    if any(config.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f"Proxy profile readback mismatch: expected={expected}, observed={config}")
    return config


def proxy_metrics(after: int = 0) -> dict:
    return proxy_request("GET", f"/metrics?after={after}")


def wait_for_proxy_event(after_id: int, generation: int, timeout: int = 30) -> dict:
    deadline = time.monotonic() + timeout
    last_metrics: dict = {}
    while time.monotonic() < deadline:
        last_metrics = proxy_metrics(after_id)
        events = last_metrics.get("events", [])
        for event in events:
            if (
                event.get("host") == EXPECTED_HOST
                and event.get("port") == 443
                and event.get("generation") == generation
                and event.get("status") == "completed"
            ):
                if event.get("upstream_ip") != EXPECTED_IP:
                    raise RuntimeError(
                        f"Proxy connected to unexpected upstream IP: expected={EXPECTED_IP}, event={event}"
                    )
                if int(event.get("bytes_upstream_to_client", 0)) < PROBE_BYTES:
                    raise RuntimeError(f"Proxy did not observe the complete fixture response: {event}")
                return event
        time.sleep(0.25)
    raise RuntimeError(
        f"No completed allowlisted proxy event for generation={generation} after event_id={after_id}: "
        f"{json.dumps(last_metrics, sort_keys=True)[:6000]}"
    )


def reset_proxy() -> dict:
    try:
        result = proxy_request("POST", "/reset")
        health = proxy_request("GET", "/health")
        config = health.get("config", {})
        verified = (
            result.get("status") == "ok"
            and config.get("label") == "baseline"
            and config.get("delay_ms") == 0
            and config.get("rate_kbps") == 0
        )
        return {"status": "verified" if verified else "unverified", "observed": config, "response": result}
    except Exception as exc:
        return {"status": "unverified", "error": str(exc)}


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


def network_probe_log_tail() -> str:
    try:
        return adb(
            "logcat", "-d", "-t", "1000", "-s",
            "BharatSimNetworkProbe:I", "BharatSimNetworkProbe:W",
            "BharatSimNetworkProbe:V", "*:S", timeout=10,
        )[-6000:]
    except Exception as exc:
        return f"Could not collect device probe logcat: {exc}"


def wait_for_probe(session: str, element_id: str, after_sequence: int, timeout: int = 60) -> dict:
    deadline = time.monotonic() + timeout
    last_text = ""
    while time.monotonic() < deadline:
        last_text = str(request("GET", f"/session/{session}/element/{element_id}/text", timeout=5).get("value", ""))
        probe = parse_probe_text(last_text)
        if probe and int(probe["sequence"]) > after_sequence:
            if int(probe["bytes_read"]) != PROBE_BYTES:
                raise RuntimeError(f"Fixture downloaded unexpected payload size: {probe['bytes_read']}")
            if probe["transport"] not in ("CELLULAR", "ETHERNET", "WIFI"):
                raise RuntimeError(f"Fixture request did not use a supported active Android transport: {probe}")
            return probe
        if "probe failed" in last_text.lower() or "returned http" in last_text.lower():
            raise RuntimeError(f"Fixture network probe failed: {last_text}\nDevice probe logcat:\n{network_probe_log_tail()}")
        time.sleep(0.5)
    raise RuntimeError(f"Fixture network probe did not complete within {timeout}s: {last_text!r}\nDevice probe logcat:\n{network_probe_log_tail()}")


def summarize_samples(samples: list[dict]) -> dict:
    durations = [int(sample["duration_ms"]) for sample in samples]
    return {
        "sample_count": len(durations),
        "successful_samples": len(durations),
        "failed_samples": 0,
        "min_ms": min(durations),
        "max_ms": max(durations),
        "spread_ms": max(durations) - min(durations),
        "median_ms": statistics.median(durations),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    journey_started_at = datetime.now(timezone.utc)
    session_id = None
    phase = "prepare_proxy_path"
    evidence: dict[str, object] = {}
    try:
        if not EXPECTED_HOST or not EXPECTED_IP:
            raise RuntimeError("BHARATSIM_PROBE_URL and BHARATSIM_PROBE_IP must be configured")
        phase = "prepare_proxy_path"
        evidence["network_preflight"] = prepare_proxy_path()
        phase = "configure_baseline_proxy"
        baseline_profile = set_proxy_profile("baseline", 0, 0)
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
                    "appium:newCommandTimeout": 60,
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

        expected_transport: str | None = None
        all_proxy_events: list[dict] = []

        def take_samples(label: str, profile: dict, previous_sequence: int) -> tuple[list[dict], int]:
            samples: list[dict] = []
            evidence["samples_" + label] = samples
            last_sequence = previous_sequence
            for _ in range(3):
                before_event_id = int(proxy_metrics()["last_event_id"])
                request("POST", base + f"/element/{action_id}/click", {})
                status = request("GET", base + f"/element/{status_id}/text").get("value")
                if status != "Primary action completed":
                    raise RuntimeError(f"Primary action state assertion failed during {label}: {status!r}")
                probe = wait_for_probe(session_id, probe_id, after_sequence=last_sequence)
                if expected_transport is not None and probe["transport"] != expected_transport:
                    raise RuntimeError(f"{label} request changed Android transport: expected={expected_transport}, observed={probe}")
                proxy_event = wait_for_proxy_event(before_event_id, int(profile["generation"]))
                if label == "latency-only":
                    expected_delay_ms = float(profile["delay_ms"])
                    injected_delay_ms = float(proxy_event.get("delay_injected_ms", 0.0))
                    delayed_directions = int(proxy_event.get("delayed_directions", 0))
                    if delayed_directions != 2 or injected_delay_ms < expected_delay_ms * 0.9:
                        raise RuntimeError(
                            "Latency-only proxy did not inject the requested RTT across both directions: "
                            f"expected_ms={expected_delay_ms}, event={proxy_event}"
                        )
                probe["proxy_event"] = proxy_event
                samples.append(probe)
                all_proxy_events.append(proxy_event)
                last_sequence = int(probe["sequence"])
            return samples, last_sequence

        # Exclude one cold-start download from all timing comparisons.
        before_warmup_event = int(proxy_metrics()["last_event_id"])
        request("POST", base + f"/element/{action_id}/click", {})
        warmup_probe = wait_for_probe(session_id, probe_id, after_sequence=0)
        expected_transport = str(warmup_probe["transport"])
        warmup_event = wait_for_proxy_event(before_warmup_event, int(baseline_profile["generation"]))
        warmup_probe["proxy_event"] = warmup_event
        all_proxy_events.append(warmup_event)
        evidence["observed_transport"] = expected_transport
        evidence["warmup_probe"] = warmup_probe

        phase = "baseline_samples"
        baseline_probes, last_sequence = take_samples("baseline", baseline_profile, int(warmup_probe["sequence"]))
        evidence["baseline_probes"] = baseline_probes

        phase = "configure_bandwidth_proxy"
        bandwidth_profile = set_proxy_profile("bandwidth-only", 0, 384)
        evidence["bandwidth_profile"] = bandwidth_profile
        phase = "bandwidth_samples"
        bandwidth_probes, last_sequence = take_samples("bandwidth-only", bandwidth_profile, last_sequence)
        evidence["bandwidth_probes"] = bandwidth_probes

        phase = "configure_latency_proxy"
        latency_profile = set_proxy_profile("latency-only", 150, 0)
        evidence["latency_profile"] = latency_profile
        phase = "latency_samples"
        latency_probes, last_sequence = take_samples("latency-only", latency_profile, last_sequence)
        evidence["latency_probes"] = latency_probes

        baseline_median_ms = statistics.median(p["duration_ms"] for p in baseline_probes)
        latency_median_ms = statistics.median(p["duration_ms"] for p in latency_probes)
        bandwidth_median_ms = statistics.median(p["duration_ms"] for p in bandwidth_probes)
        latency_delta_ms = latency_median_ms - baseline_median_ms
        bandwidth_delta_ms = bandwidth_median_ms - baseline_median_ms
        minimum_injected_latency_ms = float(latency_profile["delay_ms"]) * 0.9
        minimum_bandwidth_delta_ms = 500

        if bandwidth_delta_ms < minimum_bandwidth_delta_ms:
            raise RuntimeError(
                "Configured proxy bandwidth cap was not observed in repeated fixture downloads: "
                f"baseline={baseline_probes}, bandwidth_only={bandwidth_probes}, "
                f"baseline_median_ms={baseline_median_ms}, bandwidth_median_ms={bandwidth_median_ms}, "
                f"delta_ms={bandwidth_delta_ms}, minimum_required_delta_ms={minimum_bandwidth_delta_ms}"
            )

        phase = "verify_proxy_reset"
        reset_evidence = reset_proxy()
        evidence["reset_profile"] = reset_evidence
        if reset_evidence.get("status") != "verified":
            raise RuntimeError(f"Could not verify CONNECT proxy reset: {reset_evidence}")

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
        probe_log_text = "\n".join(probe_lines)
        observed_ips = set(re.findall(r"endpoint_ip=([0-9.]+)", probe_log_text))
        observed_hosts = set(re.findall(r"endpoint_host=([A-Za-z0-9.-]+)", probe_log_text))
        observed_proxies = set(re.findall(r"proxy_host=([0-9.]+) proxy_port=(\d+)", probe_log_text))
        expected_proxy = (os.getenv("BHARATSIM_PROXY_HOST", "10.0.2.2"), os.getenv("BHARATSIM_PROXY_PORT", "8888"))
        if not observed_ips or observed_ips != {EXPECTED_IP}:
            raise RuntimeError(f"Expected upstream IP evidence mismatch: expected={EXPECTED_IP!r}, observed={sorted(observed_ips)}")
        if not observed_hosts or observed_hosts != {EXPECTED_HOST}:
            raise RuntimeError(f"Probe endpoint host evidence mismatch: expected={EXPECTED_HOST!r}, observed={sorted(observed_hosts)}")
        if not observed_proxies or observed_proxies != {expected_proxy}:
            raise RuntimeError(f"Proxy endpoint evidence mismatch: expected={expected_proxy!r}, observed={sorted(observed_proxies)}")
        probe_logcat_path = args.artifacts / "appium-network-probe.logcat.txt"
        probe_logcat_path.write_text("\n".join(probe_lines) + "\n", encoding="utf-8")

        journey_finished_at = datetime.now(timezone.utc)
        report = {
            "schema_version": "1.0",
            "status": "passed",
            "started_at_utc": journey_started_at.isoformat(),
            "finished_at_utc": journey_finished_at.isoformat(),
            "duration_seconds": round((journey_finished_at - journey_started_at).total_seconds(), 3),
            "package_name": "org.bharatsim.smokeapp",
            "probe_endpoint": EXPECTED_URL,
            "probe_endpoint_scope": f"Fixture-only HTTPS range request to {EXPECTED_HOST}, tunneled through an allowlisted HTTP CONNECT proxy that pins upstream IP {EXPECTED_IP}. The proxy records byte counts and applies delay/rate shaping without terminating TLS. This proves the fixture path only, not arbitrary uploaded-app traffic.",
            "probe_payload_bytes": PROBE_BYTES,
            "probe_endpoint_ip": EXPECTED_IP,
            "proxy_endpoint": f"{expected_proxy[0]}:{expected_proxy[1]}",
            "proxy_control_endpoint": PROXY_CONTROL,
            "network_shaping_mode": "allowlisted HTTP CONNECT proxy",
            "observed_transport": expected_transport,
            "probe_logcat": str(probe_logcat_path),
            "assertions": [
                "the Android fixture binds its HTTPS socket to the observed Android Network and opens an explicit CONNECT tunnel to the host proxy",
                "each sample generated a completed allowlisted proxy event for raw.githubusercontent.com:443 pinned to the CI-resolved IPv4 address",
                "the proxy observed at least 64,000 response bytes for every measured sample",
                "baseline, latency-only, and bandwidth-only probes used the same Android Network transport and proxy route",
                "each latency-only proxy event recorded the requested injected RTT split across both relay directions",
                "end-to-end latency medians are retained as measurements but are not used as a deterministic pass gate because the external HTTPS endpoint has variable RTT",
                "bandwidth-only median duration exceeded baseline by at least 500 ms",
                "proxy control readback matched each requested delay/rate profile",
                "proxy settings were reset and read back at baseline",
            ],
            "baseline_profile": baseline_profile,
            "latency_profile": latency_profile,
            "bandwidth_profile": bandwidth_profile,
            "warmup_probe": warmup_probe,
            "baseline_probes": baseline_probes,
            "latency_probes": latency_probes,
            "bandwidth_probes": bandwidth_probes,
            "sample_summary": {
                "baseline": summarize_samples(baseline_probes),
                "latency_only": summarize_samples(latency_probes),
                "bandwidth_only": summarize_samples(bandwidth_probes),
            },
            "proxy_events": all_proxy_events,
            "baseline_median_ms": baseline_median_ms,
            "latency_median_ms": latency_median_ms,
            "bandwidth_median_ms": bandwidth_median_ms,
            "observed_latency_delta_ms": latency_delta_ms,
            "observed_bandwidth_delta_ms": bandwidth_delta_ms,
            "injected_latency_ms_by_sample": [
                float(p["proxy_event"].get("delay_injected_ms", 0.0)) for p in latency_probes
            ],
            "minimum_required_injected_latency_ms": minimum_injected_latency_ms,
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
        reset_after_run = reset_proxy()
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
