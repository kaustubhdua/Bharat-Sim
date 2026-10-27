#!/usr/bin/env python3
"""Polling worker for BharatSim's authenticated lease API.

Run only inside a disposable, restricted Android worker with ADB targeting a
throwaway emulator/device. This agent uses Python's standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Make both supported entry points work:
#   python -m worker.agent
#   python worker/agent.py
# Direct script execution puts worker/ rather than the repository root on
# sys.path, which otherwise breaks the absolute package import below.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worker.condition_applicator import reset_target_safely

RUNNER = ROOT / "worker" / "runner.py"
MAX_RESPONSE_BYTES = 300_000


class WorkerError(RuntimeError):
    pass


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never forward machine credentials to a redirect target."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_SAFE_OPENER = urllib.request.build_opener(NoRedirectHandler())


def safe_urlopen(request: urllib.request.Request, timeout: int):
    return _SAFE_OPENER.open(request, timeout=timeout)


def resolve_api_url(base_url: str, path: str) -> str:
    """Accept only same-origin worker API paths; never send worker credentials to a job-supplied host."""
    base = urllib.parse.urlsplit(base_url)
    candidate = urllib.parse.urlsplit(path)
    if base.scheme not in ("https", "http") or not base.hostname or base.username or base.password:
        raise WorkerError("API base URL is invalid")
    if candidate.scheme or candidate.netloc or candidate.username or candidate.password or candidate.fragment:
        raise WorkerError("worker API URL must be a relative path, not an absolute or credential-bearing URL")
    if not candidate.path.startswith("/internal/worker/") or candidate.path.startswith("//") or "\\\\" in candidate.path:
        raise WorkerError("worker API URL is outside the permitted internal worker route")
    return urllib.parse.urlunsplit((base.scheme, base.netloc, candidate.path, candidate.query, ""))


def request_json(base_url: str, token: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        resolve_api_url(base_url, path),
        data=body,
        headers={"X-BharatSim-Worker-Token": token, "Content-Type": "application/json", "Accept": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with safe_urlopen(req, timeout=timeout) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise WorkerError("API response exceeds the configured size limit")
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise WorkerError("API returned a non-object JSON response")
    return value


def download_apk(base_url: str, token: str, job: dict[str, Any], target: Path) -> None:
    path = str(job["apk_url"])
    req = urllib.request.Request(
        resolve_api_url(base_url, path),
        headers={
            "X-BharatSim-Worker-Token": token,
            "X-BharatSim-Lease-Token": str(job["lease_token"]),
            "Accept": "application/vnd.android.package-archive",
        },
    )
    total = 0
    digest = hashlib.sha256()
    with safe_urlopen(req, timeout=60) as response, target.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > 150 * 1024 * 1024:
                raise WorkerError("Downloaded APK exceeds the 150 MiB worker limit")
            digest.update(chunk)
            output.write(chunk)
    if total == 0:
        raise WorkerError("API returned an empty APK")
    expected = str(job.get("apk_sha256") or "")
    if len(expected) != 64 or digest.hexdigest() != expected:
        target.unlink(missing_ok=True)
        raise WorkerError("Downloaded APK SHA-256 does not match the queued run")


_SENSITIVE_TEXT_PATTERNS = (
    # Authorization headers and bearer tokens.
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    # Common key/value formats, including JSON-ish log fragments.
    (
        re.compile(
            r"""(?i)(["']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret|client[_-]?secret)["']?\s*[:=]\s*["']?)([^"'\s,;&}]+)(["']?)"""
        ),
        r"\1[REDACTED]\3",
    ),
    (re.compile(r"(?i)([?&](?:token|key|secret|password|api_key|access_token)=)[^&\s]+"), r"\1[REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[REDACTED_JWT]"),
)


def redact_sensitive_text(value: str) -> str:
    """Redact common credentials before worker logs become persisted run evidence."""
    for pattern, replacement in _SENSITIVE_TEXT_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def redact_report_text(value: Any) -> Any:
    """Redact string fields recursively without altering numeric or boolean evidence."""
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [redact_report_text(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_report_text(item) for key, item in value.items()}
    return value

def annotate_execution_scope(report: dict[str, Any], job: dict[str, Any]) -> None:
    """Make the distinction between smoke execution and constraint validation explicit."""
    report["execution_scope"] = "install_launch_logcat_smoke"
    report["result_interpretation"] = (
        "Smoke procedure completed; this does not prove the app is healthy "
        "or that the selected persona constraints were applied."
    )
    report["requested_persona_id"] = str(job.get("persona_id") or "unknown")
    report["constraints_applied"] = False
    network_profile = report.get("network_profile")
    control_plane = network_profile.get("control_plane", {}) if isinstance(network_profile, dict) else {}
    if isinstance(control_plane, dict) and control_plane.get("status") == "verified":
        report["network_constraints_applied"] = bool(network_profile.get("network_constraints_applied"))
        if network_profile.get("traffic_path_verified") is True:
            probe = network_profile.get("traffic_probe", {})
            report["constraint_verification"] = (
                "fixture_network_path_verified; arbitrary app traffic path is unverified, "
                "packet loss and CPU throttling remain unsupported, RAM is report-only, "
                "and battery saver and bounded storage pressure are verified only when applied"
            )
            report["result_interpretation"] = (
                "The source-built fixture received HTTP 200 over the reported emulator Ethernet/cellular "
                "transport while network controls were active. This does not prove arbitrary APK traffic "
                "uses the same path or that the app is healthy."
            )
        else:
            report["constraint_verification"] = (
                "partial_network_control_verified; active app traffic path remains unverified, "
                "packet loss and CPU throttling remain unsupported, RAM is report-only, "
                "and battery saver and bounded storage pressure are verified only when applied"
            )
            report["result_interpretation"] = (
                "Smoke procedure completed; emulator network delay/bandwidth controls were read back, "
                "battery saver and bounded storage pressure are verified only when applied, "
                "and active app traffic routing and overall app health are not proven."
            )
    else:
        report["network_constraints_applied"] = False
        report["constraint_verification"] = (
            "network_control_unverified_or_unsupported" if isinstance(network_profile, dict)
            else "unsupported_not_applied"
        )


def persona_network_cli_args(job: dict[str, Any]) -> list[str]:
    """Translate authored persona targets into validated runner arguments.

    This forwards requested values only. The runner verifies emulator control-plane
    readback and reports unsupported packet-loss/resource controls; it never treats
    a requested profile as proof that arbitrary app traffic was shaped.
    """
    profile = job.get("persona_profile")
    if profile is None or profile == {}:
        return []
    if not isinstance(profile, dict):
        raise WorkerError("persona_profile must be an object")
    try:
        latency = int(profile["latency_ms"])
        down = int(profile["down_kbps"])
        up = int(profile["up_kbps"])
        loss = float(profile.get("packet_loss_pct", 0))
    except (KeyError, TypeError, ValueError) as exc:
        raise WorkerError("persona profile is missing valid network target values") from exc
    if not 0 <= latency <= 2000:
        raise WorkerError("persona latency target is outside the supported 0–2000 ms range")
    if not 1 <= down <= 1_000_000 or not 1 <= up <= 1_000_000:
        raise WorkerError("persona throughput target is outside the supported 1–1000000 kbps range")
    if not 0 <= loss <= 100:
        raise WorkerError("persona packet-loss target must be between 0 and 100 percent")
    return [
        "--network-latency-ms", str(latency),
        "--network-down-kbps", str(down),
        "--network-up-kbps", str(up),
        "--network-loss-pct", str(loss),
    ]


def run_job(base_url: str, token: str, serial: str, job: dict[str, Any], duration: int) -> None:
    run_id = str(job["id"])
    lease_token = str(job["lease_token"])
    stop_heartbeat = threading.Event()

    def heartbeat() -> None:
        while not stop_heartbeat.wait(45):
            try:
                request_json(base_url, token, str(job["heartbeat_url"]), {"lease_token": lease_token}, timeout=15)
            except Exception as exc:
                print(f"heartbeat warning for {run_id}: {exc}", file=sys.stderr, flush=True)

    heartbeat_thread = threading.Thread(target=heartbeat, name="lease-heartbeat", daemon=True)
    heartbeat_thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="bharatsim-") as temp:
            work = Path(temp)
            apk = work / "input.apk"
            artifact_dir = work / "artifacts"
            download_apk(base_url, token, job, apk)
            env = os.environ.copy()
            env.update({
                "BHARATSIM_ENABLE_LOCAL_APK_EXECUTION": "true",
                "ANDROID_SERIAL": serial,
            })
            runner_command = [
                sys.executable, str(RUNNER), str(apk),
                "--duration", str(duration), "--out", str(artifact_dir),
            ]
            profile = job.get("persona_profile")
            if isinstance(profile, dict):
                profile_path = work / "persona_profile.json"
                profile_path.write_text(json.dumps(profile), encoding="utf-8")
                runner_command.extend(["--persona-profile", str(profile_path)])

                required_profile_values = ("latency_ms", "down_kbps", "up_kbps")
                if all(isinstance(profile.get(key), (int, float)) for key in required_profile_values):
                    runner_command.extend([
                        "--network-latency-ms", str(int(profile["latency_ms"])),
                        "--network-down-kbps", str(int(profile["down_kbps"])),
                        "--network-up-kbps", str(int(profile["up_kbps"])),
                        "--network-loss-pct", str(float(profile.get("packet_loss_pct", 0))),
                    ])
            try:
                completed = subprocess.run(
                    runner_command, env=env, capture_output=True, text=True, timeout=360, check=False,
                )
            except subprocess.TimeoutExpired as timeout_exc:
                print(f"runner timed out after 360s for run {run_id}; invoking safe cleanup fallback", file=sys.stderr, flush=True)
                reset_target_safely(serial)
                raise WorkerError("Android smoke runner timed out after 360 seconds") from timeout_exc

            reports = list(artifact_dir.glob("*.report.json"))
            if reports:
                report = json.loads(reports[0].read_text(encoding="utf-8"))
            else:
                report = {"status": "failed", "error": "Runner did not produce a report", "runner_return_code": completed.returncode}
            report.pop("device_serial", None)
            report.pop("logcat_artifact", None)
            # This metadata deliberately prevents a smoke result from being read as a health pass.
            annotate_execution_scope(report, job)
            # Keep the report well below the API's 250 KB JSON limit even with non-ASCII log text.
            for step in report.get("steps", []):
                if isinstance(step, dict):
                    for field in ("stdout_tail", "stderr_tail"):
                        if field in step:
                            step[field] = str(step[field])[-800:]
            log_files = list(artifact_dir.glob("*.logcat.txt"))
            if log_files:
                # Full artifact storage is a separate production concern.
                report["logcat_tail"] = log_files[0].read_text(encoding="utf-8", errors="replace")[-30_000:]
            report["runner_return_code"] = completed.returncode
            if completed.stderr:
                report["runner_stderr_tail"] = completed.stderr[-4_000:]
            # Logcat and subprocess output can contain bearer tokens or app secrets.
            # Redact report text before serializing it into the API's persisted result.
            report = redact_report_text(report)
            final_status = "completed" if report.get("status") == "completed" else "failed"
            error = None if final_status == "completed" else str(report.get("error") or "Android smoke runner failed")[:2000]
            request_json(base_url, token, str(job["result_url"]), {
                "lease_token": lease_token, "status": final_status, "result": report, "error": error,
            }, timeout=30)
            print(json.dumps({"run_id": run_id, "status": final_status, "apk_sha256": job.get("apk_sha256")}), flush=True)
    except Exception as exc:
        try:
            reset_target_safely(serial)
        except Exception as reset_exc:
            print(f"cleanup fallback error for {run_id}: {reset_exc}", file=sys.stderr, flush=True)
        # A failed report submission is intentionally not disguised as a successful run.
        try:
            request_json(base_url, token, str(job["result_url"]), {
                "lease_token": lease_token, "status": "failed",
                "result": {"status": "failed", "error": str(exc)[:2000]},
                "error": str(exc)[:2000],
            }, timeout=20)
        except Exception as submit_exc:
            print(f"could not submit failure for {run_id}: {submit_exc}", file=sys.stderr, flush=True)
        print(f"run {run_id} failed: {exc}", file=sys.stderr, flush=True)
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=2)


def main() -> int:
    base_url = os.getenv("BHARATSIM_API_URL", "").strip()
    token = os.getenv("BHARATSIM_WORKER_TOKEN", "").strip()
    serial = os.getenv("ANDROID_SERIAL", "").strip()
    worker_id = os.getenv("BHARATSIM_WORKER_ID", socket.gethostname()).strip()
    poll_seconds = int(os.getenv("BHARATSIM_POLL_SECONDS", "5"))
    duration = int(os.getenv("BHARATSIM_SMOKE_DURATION_SECONDS", "20"))
    if not base_url.startswith("https://") and not (base_url.startswith("http://") and os.getenv("BHARATSIM_ALLOW_INSECURE_HTTP") == "true"):
        print("BHARATSIM_API_URL must use HTTPS (HTTP is allowed only with BHARATSIM_ALLOW_INSECURE_HTTP=true for local testing)", file=sys.stderr)
        return 2
    if len(token) < 32:
        print("BHARATSIM_WORKER_TOKEN must be a random secret of at least 32 characters", file=sys.stderr)
        return 2
    if not serial:
        print("ANDROID_SERIAL must explicitly identify a disposable emulator/device", file=sys.stderr)
        return 2
    if not 1 <= poll_seconds <= 60 or not 1 <= duration <= 120:
        print("poll interval must be 1-60s and smoke duration 1-120s", file=sys.stderr)
        return 2
    if os.getenv("BHARATSIM_ENABLE_LOCAL_APK_EXECUTION") != "true":
        print("Set BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true only after isolating the worker", file=sys.stderr)
        return 2
    if not RUNNER.is_file():
        print(f"Runner not found: {RUNNER}", file=sys.stderr)
        return 2

    print(f"BharatSim worker {worker_id} starting; target device is explicitly configured.", flush=True)
    while True:
        try:
            response = request_json(base_url, token, "/internal/worker/claim", {"worker_id": worker_id}, timeout=20)
            job = response.get("job")
            if not job:
                time.sleep(poll_seconds)
                continue
            print(f"claimed run {job.get('id')} attempt {job.get('attempt')}", flush=True)
            run_job(base_url, token, serial, job, duration)
        except KeyboardInterrupt:
            return 0
        except urllib.error.HTTPError as exc:
            print(f"worker API HTTP error {exc.code}: {exc.reason}", file=sys.stderr, flush=True)
            time.sleep(min(30, poll_seconds * 2))
        except Exception as exc:
            print(f"worker loop error: {exc}", file=sys.stderr, flush=True)
            time.sleep(min(30, poll_seconds * 2))


if __name__ == "__main__":
    raise SystemExit(main())
