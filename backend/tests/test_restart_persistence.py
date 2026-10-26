"""Exercise persisted run metadata across real API process restarts.

The APK bytes are a tiny APK-shaped test fixture accepted by the upload
validator. This test does not install or execute the fixture.
"""
from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def apk_fixture_bytes() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", b"manifest test fixture")
        archive.writestr("classes.dex", b"dex test fixture")
    return stream.getvalue()


def multipart_run_request(base_url: str) -> urllib.request.Request:
    boundary = "----BharatSimPersistenceBoundary"
    apk = apk_fixture_bytes()
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="persona_id"\r\n\r\n'
        "baseline\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="apk"; filename="restart-test.apk"\r\n'
        "Content-Type: application/vnd.android.package-archive\r\n\r\n"
    ).encode() + apk + f"\r\n--{boundary}--\r\n".encode()
    return urllib.request.Request(
        base_url + "/api/v1/runs",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_api(data_dir: Path, port: int, log_path: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["BHARATSIM_DATA_DIR"] = str(data_dir)
    env["BHARATSIM_REQUIRE_API_KEY"] = "false"
    env.pop("BHARATSIM_API_KEY", None)
    log = log_path.open("ab")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=BACKEND,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    # Keep the file handle alive with the child until it exits.
    proc._bharatsim_log_handle = log  # type: ignore[attr-defined]
    return proc


def stop_api(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    handle = getattr(proc, "_bharatsim_log_handle", None)
    if handle is not None:
        handle.close()


def wait_ready(proc: subprocess.Popen, base_url: str, log_path: Path) -> None:
    deadline = time.monotonic() + 25
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(
                f"API process exited with {proc.returncode}: "
                f"{log_path.read_text(errors='replace')}"
            )
        try:
            with urllib.request.urlopen(base_url + "/health/ready", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise AssertionError(
        f"API did not become ready: {last_error}; "
        f"logs={log_path.read_text(errors='replace')}"
    )


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_run_metadata_survives_api_process_restart(tmp_path: Path) -> None:
    data_dir = tmp_path / "persistent-data"
    data_dir.mkdir()
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    log_path = tmp_path / "api.log"
    first = start_api(data_dir, port, log_path)
    try:
        wait_ready(first, base_url, log_path)
        with urllib.request.urlopen(multipart_run_request(base_url), timeout=5) as response:
            created = json.loads(response.read().decode("utf-8"))
        run_id = created["id"]
        assert created["status"] == "awaiting_worker"
        assert created["apk"]["uploaded"] is True
        assert created["apk"]["sha256"]
        assert "awaiting a worker" in created["message"]

        stop_api(first)
        first = None  # type: ignore[assignment]

        second = start_api(data_dir, port, log_path)
        try:
            wait_ready(second, base_url, log_path)
            listed = get_json(base_url + "/api/v1/runs")
            persisted = next((item for item in listed["items"] if item["id"] == run_id), None)
            assert persisted is not None, "run metadata disappeared after API restart"
            assert persisted["status"] == "awaiting_worker"
            assert persisted["persona_id"] == "baseline"
            assert persisted["apk_sha256"] == created["apk"]["sha256"]
            detail = get_json(base_url + "/api/v1/runs/" + run_id)
            assert detail["id"] == run_id
            assert detail["status"] == "awaiting_worker"
            assert detail["apk_sha256"] == created["apk"]["sha256"]
            assert detail.get("result") is None
        finally:
            stop_api(second)
    finally:
        if first is not None:
            stop_api(first)
