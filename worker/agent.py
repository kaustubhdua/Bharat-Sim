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
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
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
MAX_APK_BYTES = 500 * 1024 * 1024


def log_worker(level: str, message: str) -> None:
    """Output ISO-8601 timestamped log message for daemon and journald observability."""
    ts = datetime.now(timezone.utc).isoformat()
    stream = sys.stderr if level in ("WARN", "ERROR", "CRITICAL") else sys.stdout
    print(f"[{ts}] [{level}] {message}", file=stream, flush=True)


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
            if total > MAX_APK_BYTES:
                raise WorkerError("Downloaded APK exceeds the 500 MiB worker limit")
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
    if str(report.get("engine", "")).startswith("bharatsim-engine"):
        cons = report.get("constrained") or {}
        net = cons.get("network") or {}
        report["execution_scope"] = "baseline_vs_persona_emulator_run"
        report["requested_persona_id"] = str(job.get("persona_id") or "unknown")
        report["network_constraints_applied"] = bool(net.get("connections"))
        report["constraints_applied"] = bool(cons.get("conditions_applied"))
        report["constraint_verification"] = (
            f"{net.get('connections', 0)} app connection(s) and {net.get('bytes_down', 0)} bytes went through the "
            "shaping proxy under the persona" if net.get("connections") else
            "no app traffic passed the shaping proxy; the app may not use the network or may bypass the system proxy"
        )
        report["result_interpretation"] = (
            "Real emulator execution on a baseline and the selected persona. Metrics come from adb, dumpsys, gfxinfo, "
            "logcat and the shaping proxy; CPU throttling is not applied."
        )
        return
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
    if not 0 <= loss <= 100:
        raise WorkerError("persona packet-loss target must be between 0 and 100 percent")
    if down == 0 and up == 0:
        # Zero/zero is the authored baseline sentinel for unrestricted speed,
        # not a request to apply a zero-kbps network cap.
        return []
    if not 1 <= down <= 1_000_000 or not 1 <= up <= 1_000_000:
        raise WorkerError("persona throughput target is outside the supported 1–1000000 kbps range")
    return [
        "--network-latency-ms", str(latency),
        "--network-down-kbps", str(down),
        "--network-up-kbps", str(up),
        "--network-loss-pct", str(loss),
    ]


_SHAPER = None


def shaper():
    """One host shaping proxy per worker process; the emulator reaches it at 10.0.2.2."""
    global _SHAPER
    if _SHAPER is None:
        from worker.shaper import Shaper
        _SHAPER = Shaper(host="127.0.0.1", port=int(os.getenv("BHARATSIM_SHAPER_PORT", "8899")))
        _SHAPER.start()
    return _SHAPER


def run_job_engine(base_url: str, token: str, serial: str, job: dict[str, Any], duration: int) -> None:
    from worker.device import Device
    from worker.engine import execute

    run_id = str(job["id"])
    lease_token = str(job["lease_token"])
    stop_heartbeat = threading.Event()
    last_stage = {"text": "Claimed by worker", "sent": 0.0}

    def send(stage: str | None = None) -> None:
        payload: dict[str, Any] = {"lease_token": lease_token}
        if stage:
            payload["stage"] = stage
        request_json(base_url, token, str(job["heartbeat_url"]), payload, timeout=15)

    def heartbeat() -> None:
        while not stop_heartbeat.wait(30):
            try:
                send()
            except Exception as exc:
                print(f"heartbeat warning for {run_id}: {exc}", file=sys.stderr, flush=True)

    def stage(text: str) -> None:
        print(f"[{run_id[:8]}] {text}", flush=True)
        last_stage["text"] = text
        try:
            send(text)  # also renews the lease
        except Exception as exc:
            print(f"stage report warning: {exc}", file=sys.stderr, flush=True)

    heartbeat_thread = threading.Thread(target=heartbeat, name="lease-heartbeat", daemon=True)
    heartbeat_thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="bharatsim-") as temp:
            work = Path(temp)
            apk = work / "input.apk"
            stage("Downloading APK")
            download_apk(base_url, token, job, apk)
            report = execute(apk, job, Device(serial), shaper(), stage)
            if report.get("apk_sha256") != job.get("apk_sha256"):
                raise WorkerError("Downloaded APK hash does not match the queued artifact")
            annotate_execution_scope(report, job)
            # Logcat and subprocess output can contain bearer tokens or app secrets.
            report = redact_report_text(report)
            encoded = json.dumps(report)
            if len(encoded.encode("utf-8")) > 240_000:
                for side in ("baseline", "constrained"):
                    for f in report.get(side, {}).get("findings", []):
                        f["evidence"] = f.get("evidence", [])[:3]
                    report.get(side, {}).pop("launches", None)
            final_status = "completed" if report.get("status") == "completed" else "failed"
            error = None if final_status == "completed" else str(report.get("error") or "Execution failed")[:2000]
            request_json(base_url, token, str(job["result_url"]), {
                "lease_token": lease_token, "status": final_status, "result": report, "error": error,
            }, timeout=30)
            print(json.dumps({"run_id": run_id, "status": final_status, "score": report.get("readiness", {}).get("overall")}), flush=True)
    except Exception as exc:
        try:
            reset_target_safely(serial)
        except Exception as reset_exc:
            print(f"cleanup fallback error for {run_id}: {reset_exc}", file=sys.stderr, flush=True)
        try:
            from worker.device import Device as _D
            _D(serial).set_proxy(None)
        except Exception:
            pass
        # A failed report submission is intentionally not disguised as a successful run.
        try:
            request_json(base_url, token, str(job["result_url"]), {
                "lease_token": lease_token, "status": "failed",
                "result": {"status": "failed", "error": str(exc)[:2000], "failed_stage": last_stage["text"]},
                "error": str(exc)[:2000],
            }, timeout=20)
        except Exception as submit_exc:
            print(f"could not submit failure for {run_id}: {submit_exc}", file=sys.stderr, flush=True)
        print(f"run {run_id} failed: {exc}", file=sys.stderr, flush=True)
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=2)


def run_job_smoke(base_url: str, token: str, serial: str, job: dict[str, Any], duration: int) -> None:
    run_id = str(job["id"])
    lease_token = str(job["lease_token"])
    stop_heartbeat = threading.Event()

    def heartbeat() -> None:
        consecutive_failures = 0
        while not stop_heartbeat.wait(45):
            try:
                request_json(base_url, token, str(job["heartbeat_url"]), {"lease_token": lease_token}, timeout=15)
                consecutive_failures = 0
            except Exception as exc:
                consecutive_failures += 1
                log_worker("WARN", f"heartbeat warning for {run_id} ({consecutive_failures} consecutive failure(s)): {exc}")
                if consecutive_failures >= 3:
                    log_worker("CRITICAL", f"3 consecutive heartbeat failures for run {run_id}; lease may expire upstream")

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
                    # A baseline persona uses zero bandwidth targets to mean
                    # "unshaped/full speed". The runner's explicit CLI overrides
                    # accept only positive caps, so omit those overrides for the
                    # baseline and let the full persona profile drive condition
                    # planning (which records the control-plane reset/readback).
                    runner_command.extend(persona_network_cli_args(job))
            try:
                completed = subprocess.run(
                    runner_command, env=env, capture_output=True, text=True, timeout=360, check=False,
                    stdin=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired as timeout_exc:
                log_worker("ERROR", f"runner timed out after 360s for run {run_id}; invoking safe cleanup fallback")
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


def run_job(base_url: str, token: str, serial: str, job: dict[str, Any], duration: int) -> None:
    """Dispatch to the selected execution mode.

    BHARATSIM_WORKER_ENGINE=engine runs the full baseline-vs-persona engine
    (worker/engine.py). The default, "smoke", keeps the original install, launch
    and logcat runner (worker/runner.py)."""
    if os.getenv("BHARATSIM_WORKER_ENGINE", "smoke").strip().lower() == "engine":
        return run_job_engine(base_url, token, serial, job, duration)
    return run_job_smoke(base_url, token, serial, job, duration)


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
    if os.getenv("BHARATSIM_WORKER_ENGINE", "smoke").strip().lower() == "engine":
        try:
            from worker import ml
            ml.model()  # load (or train) the failure classifier before claiming work
            shaper()
        except Exception as exc:
            print(f"worker setup failed: {exc}", file=sys.stderr)
            return 2
    elif not RUNNER.is_file():
        print(f"Runner not found: {RUNNER}", file=sys.stderr)
        return 2

    log_worker("INFO", f"BharatSim worker {worker_id} starting; target device is explicitly configured ({serial}).")
    shutdown_requested = threading.Event()

    def handle_shutdown(signum: int, frame: Any) -> None:
        signame = "SIGTERM" if signum == getattr(signal, "SIGTERM", -1) else "SIGINT"
        log_worker("WARN", f"Received {signame}; initiating graceful shutdown...")
        shutdown_requested.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown)

    while not shutdown_requested.is_set():
        try:
            response = request_json(base_url, token, "/internal/worker/claim", {"worker_id": worker_id}, timeout=20)
            job = response.get("job")
            if not job:
                if shutdown_requested.wait(poll_seconds):
                    break
                continue
            log_worker("INFO", f"Claimed run {job.get('id')} attempt {job.get('attempt')}")
            run_job(base_url, token, serial, job, duration)
        except KeyboardInterrupt:
            break
        except urllib.error.HTTPError as exc:
            log_worker("ERROR", f"Worker API HTTP error {exc.code}: {exc.reason}")
            if shutdown_requested.wait(min(30, poll_seconds * 2)):
                break
        except Exception as exc:
            log_worker("ERROR", f"Worker loop error: {exc}")
            if shutdown_requested.wait(min(30, poll_seconds * 2)):
                break

    log_worker("INFO", "Performing safe device reset prior to worker shutdown...")
    try:
        reset_target_safely(serial)
    except Exception as reset_exc:
        log_worker("WARN", f"Device reset warning on shutdown: {reset_exc}")
    log_worker("INFO", "BharatSim worker stopped cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
