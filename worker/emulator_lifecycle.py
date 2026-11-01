"""Disposable Android Emulator lifecycle helpers for the BharatSim worker.

Production workers must wipe emulator user data between APK jobs. The worker VM
must still be dedicated and network-isolated: guest wiping is not a substitute
for a disposable host or VM snapshot boundary.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Sequence


SERIAL_RE = re.compile(r"^emulator-(\d{4})$")
AVD_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
DEFAULT_BOOT_TIMEOUT_SECONDS = 240
MIN_BOOT_TIMEOUT_SECONDS = 60
MAX_BOOT_TIMEOUT_SECONDS = 600
MAX_EMULATOR_LOG_BYTES = 10 * 1024 * 1024


def run_cmd(args: Sequence[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def parse_emulator_port(serial: str) -> int:
    match = SERIAL_RE.fullmatch(serial.strip())
    if not match:
        raise ValueError("ANDROID_SERIAL must be an emulator serial such as emulator-5554")
    port = int(match.group(1))
    if port < 5554 or port > 5684 or port % 2:
        raise ValueError("Android Emulator serial must use an even console port between 5554 and 5684")
    return port


def resolve_emulator_binary() -> str:
    configured = os.getenv("ANDROID_EMULATOR_BINARY", "").strip()
    candidates: list[str] = []
    if configured:
        candidates.append(configured)
    for root_name in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        root = os.getenv(root_name, "").strip()
        if root:
            candidates.append(str(Path(root) / "emulator" / "emulator"))
    located = shutil.which("emulator")
    if located:
        candidates.append(located)
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise RuntimeError("Android Emulator binary not found; set ANDROID_SDK_ROOT or ANDROID_EMULATOR_BINARY")


def _validate_kvm(accel: str) -> None:
    if accel not in {"on", "off"}:
        raise ValueError("BHARATSIM_EMULATOR_ACCEL must be 'on' or 'off'")
    if accel == "on":
        kvm = Path("/dev/kvm")
        if not kvm.exists() or not os.access(kvm, os.R_OK | os.W_OK):
            raise RuntimeError("Hardware-accelerated production emulator requires readable/writable /dev/kvm")


def _wait_for_device_absent(
    serial: str,
    timeout_seconds: int,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = run_cmd,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        result = run(["adb", "devices"], timeout=8)
        present = any(
            line.split() and line.split()[0] == serial
            for line in result.stdout.splitlines()[1:]
        )
        if result.returncode == 0 and not present:
            return
        sleep(1)
    raise RuntimeError(f"Existing emulator {serial} did not stop after the kill request")


def _wait_for_emulator_ready(
    serial: str,
    process: subprocess.Popen[bytes],
    timeout_seconds: int,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = run_cmd,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    deadline = monotonic() + timeout_seconds
    last_state = "not connected"
    while monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"New emulator process exited early (code {process.returncode})")
        state = run(["adb", "-s", serial, "get-state"], timeout=8)
        last_state = state.stdout.strip() or state.stderr.strip() or "not connected"
        if state.returncode == 0 and state.stdout.strip() == "device":
            boot = run(
                ["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"],
                timeout=8,
            )
            if boot.returncode == 0 and boot.stdout.strip() == "1":
                package_manager = run(
                    ["adb", "-s", serial, "shell", "pm", "path", "android"],
                    timeout=10,
                )
                if package_manager.returncode == 0 and "package:" in package_manager.stdout:
                    return
        sleep(2)
    raise RuntimeError(
        f"Emulator {serial} did not complete boot within {timeout_seconds}s; last ADB state: {last_state}"
    )


def recycle_emulator(
    serial: str,
    avd_name: str,
    *,
    boot_timeout_seconds: int | None = None,
    emulator_binary: str | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = run_cmd,
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    """Stop the current AVD and start a clean instance with -wipe-data.

    The ADB serial/console port is preserved so the worker agent can continue
    polling the API without changing its worker registration.
    """
    port = parse_emulator_port(serial)
    avd_name = avd_name.strip()
    if not AVD_NAME_RE.fullmatch(avd_name):
        raise ValueError("ANDROID_AVD_NAME contains unsupported characters or is empty")

    timeout = boot_timeout_seconds
    if timeout is None:
        try:
            timeout = int(os.getenv("BHARATSIM_EMULATOR_BOOT_TIMEOUT_SECONDS", str(DEFAULT_BOOT_TIMEOUT_SECONDS)))
        except ValueError as exc:
            raise ValueError("BHARATSIM_EMULATOR_BOOT_TIMEOUT_SECONDS must be an integer") from exc
    if not MIN_BOOT_TIMEOUT_SECONDS <= timeout <= MAX_BOOT_TIMEOUT_SECONDS:
        raise ValueError(
            f"Emulator boot timeout must be between {MIN_BOOT_TIMEOUT_SECONDS} and {MAX_BOOT_TIMEOUT_SECONDS} seconds"
        )

    accel = os.getenv("BHARATSIM_EMULATOR_ACCEL", "on").strip().lower()
    _validate_kvm(accel)
    binary = emulator_binary or resolve_emulator_binary()

    avds = run([binary, "-list-avds"], timeout=20)
    if avds.returncode != 0 or avd_name not in {line.strip() for line in avds.stdout.splitlines()}:
        raise RuntimeError(f"Configured Android AVD '{avd_name}' was not found by {binary} -list-avds")

    run(["adb", "start-server"], timeout=15)
    # A missing old device is acceptable on first startup. If one is present,
    # kill it and wait until ADB no longer lists the serial before reusing it.
    run(["adb", "-s", serial, "emu", "kill"], timeout=15)
    _wait_for_device_absent(serial, 45, run=run, sleep=sleep, monotonic=monotonic)

    log_path = Path(os.getenv("BHARATSIM_EMULATOR_LOG", "/tmp/bharatsim-emulator.log"))
    if log_path.is_symlink():
        raise RuntimeError("BHARATSIM_EMULATOR_LOG must not be a symbolic link")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists() and log_path.stat().st_size >= MAX_EMULATOR_LOG_BYTES:
        rotated = log_path.with_suffix(log_path.suffix + ".1")
        if rotated.exists():
            rotated.unlink()
        log_path.replace(rotated)
    command = [
        binary,
        "-avd", avd_name,
        "-port", str(port),
        "-wipe-data",
        "-no-snapshot",
        "-no-window",
        "-no-audio",
        "-no-boot-anim",
        "-gpu", "swiftshader_indirect",
        "-accel", accel,
    ]
    with log_path.open("ab") as log_file:
        process = popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )
    try:
        _wait_for_emulator_ready(
            serial,
            process,
            timeout,
            run=run,
            sleep=sleep,
            monotonic=monotonic,
        )
    except Exception:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        raise

    return {
        "status": "verified",
        "serial": serial,
        "avd_name": avd_name,
        "port": port,
        "wipe_data": True,
        "snapshot_reused": False,
        "boot_completed": True,
        "pid": process.pid,
        "log_path": str(log_path),
    }
