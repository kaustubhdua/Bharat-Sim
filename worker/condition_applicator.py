#!/usr/bin/env python3
"""Centralized condition applicator and lifecycle manager for BharatSim.

Applies supported persona conditions to disposable Android targets, verifies state
readback, records evidence truthfully, and guarantees cleanup on completion or failure.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any, Callable

from worker.condition_planner import ConditionPlan, is_emulator_serial

STORAGE_PRESSURE_FILE = "/data/local/tmp/bharatsim_storage_pressure.tmp"
DEFAULT_SAFETY_RESERVE_MB = 100
DEFAULT_MAX_ALLOCATION_MB = 2048


def default_run_cmd(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    """Default subprocess runner capturing text output."""
    try:
        resolved_args = list(args)
        if resolved_args and resolved_args[0] == "adb" and not shutil.which("adb"):
            sdk_adb = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
            if os.path.isfile(sdk_adb):
                resolved_args[0] = sdk_adb
        return subprocess.run(resolved_args, capture_output=True, text=True, timeout=timeout, check=False)
    except OSError as exc:
        return subprocess.CompletedProcess(args=args, returncode=127, stdout="", stderr=str(exc))


def parse_df_available_mb(output: str) -> int | None:
    """Parse free/available storage in MB from Android df output.

    Handles toolbox and toybox df output for /data mount points.
    """
    for line in output.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("filesystem"):
            continue
        # Check if line corresponds to /data
        parts = line.split()
        if len(parts) >= 4 and any("/data" in p for p in parts):
            # Formats typically have:
            # Filesystem 1K-blocks Used Available Use% Mounted
            # or Filesystem Blocks Used Free
            # Available/Free is usually index 3 (or index 3 from end)
            try:
                # Look for the available column which is numeric
                # In standard toybox df -k: [Filesystem, 1K-blocks, Used, Available, Use%, Mounted on]
                if len(parts) >= 5 and parts[3].isdigit():
                    avail_kb = int(parts[3])
                    return avail_kb // 1024
                # In some toybox df without -k, it might be in blocks (1024 or 512 bytes)
                for part in parts[1:4]:
                    if part.isdigit():
                        return int(part) // 1024
            except (ValueError, IndexError):
                continue
    return None


def get_free_storage_mb(
    serial: str, run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None
) -> int | None:
    """Read available space on the /data partition in megabytes."""
    runner = run_cmd_fn or default_run_cmd
    res = runner(["adb", "-s", serial, "shell", "df", "-k", "/data"], timeout=15)
    if res.returncode == 0:
        parsed = parse_df_available_mb(res.stdout)
        if parsed is not None:
            return parsed
    # Fallback to plain df /data
    res = runner(["adb", "-s", serial, "shell", "df", "/data"], timeout=15)
    if res.returncode == 0:
        return parse_df_available_mb(res.stdout)
    return None


def parse_meminfo_mb(output: str) -> dict[str, int]:
    """Extract MemTotal and MemAvailable from /proc/meminfo text."""
    result: dict[str, int] = {}
    total_match = re.search(r"MemTotal:\s+(\d+)\s+kB", output, re.I)
    if total_match:
        result["total_ram_mb"] = int(total_match.group(1)) // 1024
    avail_match = re.search(r"MemAvailable:\s+(\d+)\s+kB", output, re.I)
    if avail_match:
        result["available_ram_mb"] = int(avail_match.group(1)) // 1024
    else:
        free_match = re.search(r"MemFree:\s+(\d+)\s+kB", output, re.I)
        if free_match:
            result["available_ram_mb"] = int(free_match.group(1)) // 1024
    return result


def get_device_meminfo(
    serial: str, run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None
) -> dict[str, int]:
    """Query memory information from the target device."""
    runner = run_cmd_fn or default_run_cmd
    res = runner(["adb", "-s", serial, "shell", "cat", "/proc/meminfo"], timeout=10)
    if res.returncode == 0:
        return parse_meminfo_mb(res.stdout)
    return {}


def apply_battery_saver(
    serial: str, run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None
) -> dict[str, Any]:
    """Apply battery saver mode on an Android emulator and verify readback."""
    runner = run_cmd_fn or default_run_cmd
    if not is_emulator_serial(serial):
        return {
            "apply_status": "unsupported",
            "verification_status": "unsupported",
            "reason": "Battery saver control is restricted to disposable Android emulators",
        }

    unplug_res = runner(["adb", "-s", serial, "shell", "cmd", "battery", "unplug"], timeout=15)
    low_power_res = runner(
        ["adb", "-s", serial, "shell", "settings", "put", "global", "low_power", "1"], timeout=15
    )

    verify_res = runner(
        ["adb", "-s", serial, "shell", "settings", "get", "global", "low_power"], timeout=15
    )
    verified = (
        unplug_res.returncode == 0
        and low_power_res.returncode == 0
        and verify_res.returncode == 0
        and verify_res.stdout.strip() == "1"
    )

    dumpsys_res = runner(["adb", "-s", serial, "shell", "dumpsys", "battery"], timeout=15)

    return {
        "apply_status": "applied" if (unplug_res.returncode == 0 and low_power_res.returncode == 0) else "failed",
        "verification_status": "verified" if verified else "unverified",
        "commands": {
            "battery_unplug_rc": unplug_res.returncode,
            "low_power_rc": low_power_res.returncode,
            "verify_rc": verify_res.returncode,
            "readback_low_power": verify_res.stdout.strip() if verify_res.returncode == 0 else None,
        },
        "battery_dumpsys_tail": dumpsys_res.stdout[-500:] if dumpsys_res.returncode == 0 else "",
        "reason": (
            "Battery saver active and verified via settings readback"
            if verified
            else "Failed to apply or verify battery saver low_power setting"
        ),
    }


def reset_battery_saver(
    serial: str, run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None
) -> dict[str, Any]:
    """Reset battery saver mode and restore standard battery charging state."""
    runner = run_cmd_fn or default_run_cmd
    if not is_emulator_serial(serial):
        return {"status": "not_applicable", "reason": "Target is not an Android emulator"}

    reset_cmd = runner(["adb", "-s", serial, "shell", "cmd", "battery", "reset"], timeout=15)
    low_power_cmd = runner(
        ["adb", "-s", serial, "shell", "settings", "put", "global", "low_power", "0"], timeout=15
    )
    verify_res = runner(
        ["adb", "-s", serial, "shell", "settings", "get", "global", "low_power"], timeout=15
    )

    restored = (
        reset_cmd.returncode == 0
        and low_power_cmd.returncode == 0
        and verify_res.returncode == 0
        and verify_res.stdout.strip() == "0"
    )

    return {
        "status": "verified" if restored else "unverified",
        "readback_low_power": verify_res.stdout.strip() if verify_res.returncode == 0 else None,
        "commands_return_codes": [reset_cmd.returncode, low_power_cmd.returncode, verify_res.returncode],
    }


def apply_storage_pressure(
    serial: str,
    target_free_mb: int,
    safety_reserve_mb: int = DEFAULT_SAFETY_RESERVE_MB,
    max_allocation_mb: int = DEFAULT_MAX_ALLOCATION_MB,
    temp_file: str = STORAGE_PRESSURE_FILE,
    tolerance_mb: int = 50,
    run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Safely apply bounded temporary storage pressure toward a target free space budget.

    Semantics:
    - If initial free storage is already at or below target, target is satisfied without allocation.
    - If initial free storage is at or below safety reserve, allocation is skipped to protect OS stability.
    - If bounded safety limits (max_allocation_mb or safety_reserve_mb) prevent reaching the target,
      bounded pressure is applied and reported as apply_status="partially_applied", verification_status="verified",
      target_reached=False, with explicit limitation reasons.
    - If target free space is achieved within tolerance_mb, reported as apply_status="applied", verification_status="verified",
      target_reached=True.
    - If allocation fails (dd error or file missing), reported as apply_status="failed", verification_status="unverified".
    """
    runner = run_cmd_fn or default_run_cmd
    if not is_emulator_serial(serial):
        return {
            "apply_status": "unsupported",
            "verification_status": "unsupported",
            "target_reached": False,
            "bounded_pressure_applied": False,
            "requested_target_mb": target_free_mb,
            "actual_achieved_free_mb": None,
            "safety_reserve_mb": safety_reserve_mb,
            "max_allocation_mb": max_allocation_mb,
            "limitation_reason": "Target is not an Android emulator serial",
            "reason": "Storage pressure simulation is restricted to disposable Android emulators",
        }

    initial_free = get_free_storage_mb(serial, runner)
    if initial_free is None:
        return {
            "apply_status": "failed",
            "verification_status": "unverified",
            "target_reached": False,
            "bounded_pressure_applied": False,
            "requested_target_mb": target_free_mb,
            "actual_achieved_free_mb": None,
            "safety_reserve_mb": safety_reserve_mb,
            "max_allocation_mb": max_allocation_mb,
            "limitation_reason": "Could not determine initial free storage on /data partition",
            "reason": "Could not determine initial free storage on /data partition",
        }

    if initial_free <= target_free_mb:
        return {
            # The target state already exists. Do not claim BharatSim applied
            # pressure when it did not write any bytes to the device.
            "apply_status": "already_satisfied",
            "verification_status": "verified",
            "condition_state": "preexisting_target_satisfied",
            "target_reached": True,
            "bounded_pressure_applied": False,
            "allocated_mb": 0,
            "requested_target_mb": target_free_mb,
            "actual_achieved_free_mb": initial_free,
            "target_free_mb": target_free_mb,
            "initial_free_mb": initial_free,
            "current_free_mb": initial_free,
            "post_allocation_free_mb": initial_free,
            "safety_reserve_mb": safety_reserve_mb,
            "max_allocation_mb": max_allocation_mb,
            "limitation_reason": None,
            "reason": (
                f"Initial free storage ({initial_free} MB) is already at or below target ({target_free_mb} MB); "
                "target satisfied without allocation"
            ),
        }

    desired_allocation = initial_free - target_free_mb
    max_safe_allocation = max(0, initial_free - safety_reserve_mb)
    allocated_mb = min(desired_allocation, max_safe_allocation, max_allocation_mb)

    if allocated_mb <= 0:
        return {
            "apply_status": "skipped",
            "verification_status": "unverified",
            "target_reached": False,
            "bounded_pressure_applied": False,
            "allocated_mb": 0,
            "requested_target_mb": target_free_mb,
            "actual_achieved_free_mb": initial_free,
            "target_free_mb": target_free_mb,
            "initial_free_mb": initial_free,
            "safety_reserve_mb": safety_reserve_mb,
            "max_allocation_mb": max_allocation_mb,
            "limitation_reason": (
                f"Safety reserve of {safety_reserve_mb} MB prevents any allocation "
                f"(initial free storage is {initial_free} MB)"
            ),
            "reason": (
                f"Cannot safely allocate storage pressure without breaching safety reserve of {safety_reserve_mb} MB "
                f"(initial free storage is {initial_free} MB)"
            ),
        }

    # Allocate bounded temporary file using dd
    alloc_cmd = runner(
        [
            "adb",
            "-s",
            serial,
            "shell",
            "dd",
            "if=/dev/zero",
            f"of={temp_file}",
            "bs=1048576",
            f"count={allocated_mb}",
        ],
        timeout=60,
    )

    post_free = get_free_storage_mb(serial, runner)

    # Check that file exists on device
    check_file = runner(["adb", "-s", serial, "shell", "ls", "-l", temp_file], timeout=15)
    file_exists = check_file.returncode == 0 and "No such file" not in check_file.stdout

    allocation_ok = bool(
        alloc_cmd.returncode == 0
        and file_exists
        and post_free is not None
        and post_free < initial_free
    )

    if not allocation_ok:
        return {
            "apply_status": "failed",
            "verification_status": "unverified",
            "target_reached": False,
            "bounded_pressure_applied": False,
            "allocated_mb": allocated_mb if file_exists else 0,
            "requested_target_mb": target_free_mb,
            "actual_achieved_free_mb": post_free,
            "target_free_mb": target_free_mb,
            "initial_free_mb": initial_free,
            "post_allocation_free_mb": post_free,
            "safety_reserve_mb": safety_reserve_mb,
            "max_allocation_mb": max_allocation_mb,
            "temp_file": temp_file,
            "dd_return_code": alloc_cmd.returncode,
            "limitation_reason": "dd allocation command failed or pressure file was not created",
            "reason": f"Failed to allocate temporary storage pressure file via dd (rc={alloc_cmd.returncode})",
        }

    # Bounded pressure was successfully applied
    bounded_pressure_applied = True

    # Check whether the requested target free space was actually reached within tolerance
    target_reached = bool(post_free is not None and post_free <= target_free_mb + tolerance_mb)

    if target_reached:
        apply_status = "applied"
        verification_status = "verified"
        limitation_reason = None
        reason = (
            f"Storage pressure successfully applied: allocated {allocated_mb} MB temporary file; "
            f"free storage reduced from {initial_free} MB to {post_free} MB "
            f"(target {target_free_mb} MB reached within {tolerance_mb} MB tolerance)"
        )
    else:
        # Bounded limits prevented reaching the exact requested target
        apply_status = "partially_applied"
        verification_status = "verified"
        if allocated_mb == max_allocation_mb and desired_allocation > max_allocation_mb:
            limitation_reason = (
                f"Bounded allocation cap of {max_allocation_mb} MB reached before achieving target {target_free_mb} MB "
                f"(would require allocating {desired_allocation} MB from initial {initial_free} MB free; achieved {post_free} MB free)"
            )
        elif allocated_mb == max_safe_allocation and desired_allocation > max_safe_allocation:
            limitation_reason = (
                f"Safety reserve of {safety_reserve_mb} MB prevented allocating full {desired_allocation} MB "
                f"to reach target {target_free_mb} MB (achieved {post_free} MB free)"
            )
        else:
            limitation_reason = (
                f"Achieved free storage ({post_free} MB) exceeded requested target ({target_free_mb} MB) "
                f"after allocating {allocated_mb} MB"
            )
        reason = (
            f"Bounded storage pressure was successfully applied ({allocated_mb} MB allocated, "
            f"free reduced from {initial_free} MB to {post_free} MB), but requested target of "
            f"{target_free_mb} MB free could not be fully reached: {limitation_reason}"
        )

    return {
        "apply_status": apply_status,
        "verification_status": verification_status,
        "target_reached": target_reached,
        "bounded_pressure_applied": bounded_pressure_applied,
        "requested_target_mb": target_free_mb,
        "actual_achieved_free_mb": post_free,
        "target_free_mb": target_free_mb,
        "initial_free_mb": initial_free,
        "allocated_mb": allocated_mb,
        "post_allocation_free_mb": post_free,
        "safety_reserve_mb": safety_reserve_mb,
        "max_allocation_mb": max_allocation_mb,
        "limitation_reason": limitation_reason,
        "temp_file": temp_file,
        "dd_return_code": alloc_cmd.returncode,
        "reason": reason,
    }


def reset_storage_pressure(
    serial: str,
    temp_file: str = STORAGE_PRESSURE_FILE,
    run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Remove temporary storage pressure file and verify removal.

    Primary cleanup guarantee is verified removal of the temporary pressure file.
    Post-cleanup free storage is recorded for diagnostic evidence only; cleanup is
    never failed due to minor background OS filesystem space variations.
    """
    runner = run_cmd_fn or default_run_cmd
    if not is_emulator_serial(serial):
        return {"status": "not_applicable", "reason": "Target is not an Android emulator"}

    # Diagnostic measurement of free space before removal
    free_mb_before = get_free_storage_mb(serial, runner)

    rm_cmd = runner(["adb", "-s", serial, "shell", "rm", "-f", temp_file], timeout=15)
    check_cmd = runner(["adb", "-s", serial, "shell", "ls", temp_file], timeout=15)
    file_removed = check_cmd.returncode != 0 or "No such file" in (check_cmd.stdout + check_cmd.stderr)

    free_mb_after = get_free_storage_mb(serial, runner)

    # Primary verification is strictly that the allocated temporary file has been deleted
    status = "verified" if file_removed else "unverified"

    return {
        "status": status,
        "rm_return_code": rm_cmd.returncode,
        "file_removed": file_removed,
        "file_removed_verified": file_removed,
        "free_storage_mb_before_cleanup": free_mb_before,
        "free_storage_mb_after_cleanup": free_mb_after,
        "reason": (
            "Temporary storage pressure file successfully removed and verified absent from filesystem"
            if file_removed
            else f"Failed to verify removal of temporary storage pressure file: {temp_file}"
        ),
    }


def reset_target_safely(
    serial: str, run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None
) -> dict[str, Any]:
    """Guaranteed safe reset fallback for a disposable Android target.

    Can be invoked by runner or by agent after timeouts or unhandled exceptions.
    Restores emulator network, battery saver, and removes temporary storage files.
    Does NOT execute broad or destructive ADB commands.
    """
    runner = run_cmd_fn or default_run_cmd
    if not is_emulator_serial(serial):
        return {"status": "not_applicable", "reason": "Target is not an Android emulator serial"}

    # 1. Reset network controls
    # Lazily import runner reset to avoid circular dependency
    try:
        from worker.runner import reset_emulator_network_profile

        net_reset = reset_emulator_network_profile(serial)
    except Exception as exc:
        delay = runner(["adb", "-s", serial, "emu", "network", "delay", "none"], timeout=15)
        speed = runner(["adb", "-s", serial, "emu", "network", "speed", "full"], timeout=15)
        net_reset = {
            "status": "fallback_executed",
            "commands_return_codes": [delay.returncode, speed.returncode],
            "error": str(exc),
        }

    # 2. Reset battery saver
    battery_reset = reset_battery_saver(serial, runner)

    # 3. Clean up storage pressure file
    storage_reset = reset_storage_pressure(serial, STORAGE_PRESSURE_FILE, runner)

    all_verified = (
        net_reset.get("status") == "verified"
        and battery_reset.get("status") == "verified"
        and storage_reset.get("status") == "verified"
    )

    return {
        "status": "verified" if all_verified else "partial",
        "network": net_reset,
        "battery_saver": battery_reset,
        "storage": storage_reset,
    }


class ConditionManager:
    """Context manager governing the condition simulation lifecycle on Android targets."""

    def __init__(
        self,
        serial: str,
        plan: ConditionPlan,
        run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        apply_network_fn: Callable[..., dict[str, Any]] | None = None,
        reset_network_fn: Callable[..., dict[str, Any]] | None = None,
    ):
        self.serial = serial
        self.plan = plan
        self.run_cmd = run_cmd_fn or default_run_cmd
        self._apply_network_fn = apply_network_fn
        self._reset_network_fn = reset_network_fn
        self.applied_conditions: list[str] = []
        self.partially_applied_conditions: list[str] = []
        self.cleanup_needed: set[str] = set()
        self.condition_records: list[dict[str, Any]] = []
        self.cleanup_records: dict[str, Any] = {}
        self.network_profile_evidence: dict[str, Any] | None = None
        self._applied = False
        self._cleaned_up = False

    def __enter__(self) -> ConditionManager:
        self.apply_and_verify()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.cleanup_and_verify()
        # Return False to re-raise any exception that occurred inside the with block
        return False

    def apply_and_verify(self) -> dict[str, Any]:
        """Apply all supported conditions in the plan and verify readback."""
        if self._applied:
            return self.get_evidence()
        self._applied = True

        # Process each planned condition
        for condition in self.plan.conditions:
            name = condition.name

            # 1. Network conditions (latency, download, upload, packet loss)
            if name in ("network_latency", "download_bandwidth", "upload_bandwidth", "packet_loss"):
                # Network profile is applied via existing apply_emulator_network_profile
                if self.network_profile_evidence is None:
                    lat_cond = self.plan.get_condition("network_latency")
                    down_cond = self.plan.get_condition("download_bandwidth")
                    up_cond = self.plan.get_condition("upload_bandwidth")
                    loss_cond = self.plan.get_condition("packet_loss")

                    lat = lat_cond.target_value if (lat_cond and lat_cond.requested) else 0
                    down = down_cond.target_value if (down_cond and down_cond.requested) else 1000000
                    up = up_cond.target_value if (up_cond and up_cond.requested) else 1000000
                    loss = loss_cond.target_value if (loss_cond and loss_cond.requested) else 0.0

                    # Only invoke if at least one network control was requested
                    if any(
                        c and c.requested
                        for c in (lat_cond, down_cond, up_cond, loss_cond)
                    ):
                        if self._apply_network_fn:
                            net_ev = self._apply_network_fn(self.serial, lat, down, up, loss)
                        else:
                            from worker.runner import apply_emulator_network_profile

                            net_ev = apply_emulator_network_profile(self.serial, lat, down, up, loss)
                        self.network_profile_evidence = net_ev
                    else:
                        self.network_profile_evidence = None

                # Record individual condition evidence
                if not condition.requested:
                    self.condition_records.append({
                        "condition": name,
                        "requested": False,
                        "target": None,
                        "apply_status": "not_requested",
                        "verification_status": "not_applicable",
                        "cleanup_status": "not_applicable",
                        "reason": condition.reason,
                    })
                elif name == "packet_loss":
                    self.condition_records.append({
                        "condition": name,
                        "requested": True,
                        "target": condition.target_value,
                        "apply_status": "unsupported",
                        "verification_status": "unsupported",
                        "cleanup_status": "not_applicable",
                        "reason": condition.reason,
                    })
                else:
                    cp_verified = (
                        isinstance(self.network_profile_evidence, dict)
                        and self.network_profile_evidence.get("control_plane", {}).get("status") == "verified"
                    )
                    if name in ("network_latency", "download_bandwidth"):
                        status = "verified" if cp_verified else "unverified"
                    else:  # upload_bandwidth
                        status = "control_plane_verified" if cp_verified else "unverified"

                    if cp_verified:
                        if name not in self.applied_conditions:
                            self.applied_conditions.append(name)
                        self.cleanup_needed.add(name)

                    self.condition_records.append({
                        "condition": name,
                        "requested": True,
                        "target": condition.target_value,
                        "apply_status": "applied" if cp_verified else "failed",
                        "verification_status": status,
                        "cleanup_status": "pending" if cp_verified else "not_applicable",
                        "reason": (
                            f"{name} control-plane verified on emulator console"
                            if cp_verified
                            else "Control plane readback verification failed or target is not an emulator"
                        ),
                    })

            # 2. Battery saver
            elif name == "battery_saver":
                if not condition.requested:
                    self.condition_records.append({
                        "condition": name,
                        "requested": False,
                        "target": False,
                        "apply_status": "not_requested",
                        "verification_status": "not_applicable",
                        "cleanup_status": "not_applicable",
                        "reason": condition.reason,
                    })
                elif not self.plan.is_emulator:
                    self.condition_records.append({
                        "condition": name,
                        "requested": True,
                        "target": True,
                        "apply_status": "unsupported",
                        "verification_status": "unsupported",
                        "cleanup_status": "not_applicable",
                        "reason": condition.reason,
                    })
                else:
                    bat_ev = apply_battery_saver(self.serial, self.run_cmd)
                    if bat_ev["apply_status"] == "applied":
                        self.applied_conditions.append(name)
                        self.cleanup_needed.add(name)
                    self.condition_records.append({
                        "condition": name,
                        "requested": True,
                        "target": True,
                        "apply_status": bat_ev["apply_status"],
                        "verification_status": bat_ev["verification_status"],
                        "cleanup_status": "pending" if bat_ev["apply_status"] == "applied" else "not_applicable",
                        "reason": bat_ev["reason"],
                        "details": bat_ev.get("commands", {}),
                    })

            # 3. Storage pressure
            elif name == "storage_pressure":
                if not condition.requested:
                    self.condition_records.append({
                        "condition": name,
                        "requested": False,
                        "target": None,
                        "apply_status": "not_requested",
                        "verification_status": "not_applicable",
                        "cleanup_status": "not_applicable",
                        "reason": condition.reason,
                    })
                elif not self.plan.is_emulator:
                    self.condition_records.append({
                        "condition": name,
                        "requested": True,
                        "target": condition.target_value,
                        "apply_status": "unsupported",
                        "verification_status": "unsupported",
                        "cleanup_status": "not_applicable",
                        "reason": condition.reason,
                    })
                else:
                    target_mb = int(condition.target_value)
                    stor_ev = apply_storage_pressure(
                        self.serial,
                        target_free_mb=target_mb,
                        safety_reserve_mb=condition.parameters.get("safety_reserve_mb", DEFAULT_SAFETY_RESERVE_MB),
                        max_allocation_mb=condition.parameters.get("max_allocation_mb", DEFAULT_MAX_ALLOCATION_MB),
                        temp_file=condition.parameters.get("temp_file_path", STORAGE_PRESSURE_FILE),
                        run_cmd_fn=self.run_cmd,
                    )
                    if stor_ev["apply_status"] == "applied":
                        self.applied_conditions.append(name)
                        if stor_ev.get("allocated_mb", 0) > 0:
                            self.cleanup_needed.add(name)
                    elif stor_ev["apply_status"] == "partially_applied":
                        self.partially_applied_conditions.append(name)
                        if stor_ev.get("allocated_mb", 0) > 0:
                            self.cleanup_needed.add(name)

                    self.condition_records.append({
                        "condition": name,
                        "requested": True,
                        "target": target_mb,
                        "apply_status": stor_ev["apply_status"],
                        "verification_status": stor_ev["verification_status"],
                        "target_reached": stor_ev.get("target_reached", False),
                        "bounded_pressure_applied": stor_ev.get("bounded_pressure_applied", False),
                        "requested_target_mb": stor_ev.get("requested_target_mb", target_mb),
                        "actual_achieved_free_mb": stor_ev.get("actual_achieved_free_mb"),
                        "safety_reserve_mb": stor_ev.get("safety_reserve_mb"),
                        "max_allocation_mb": stor_ev.get("max_allocation_mb"),
                        "limitation_reason": stor_ev.get("limitation_reason"),
                        "cleanup_status": "pending" if (name in self.cleanup_needed) else "not_applicable",
                        "reason": stor_ev["reason"],
                        "details": {
                            "initial_free_mb": stor_ev.get("initial_free_mb"),
                            "allocated_mb": stor_ev.get("allocated_mb"),
                            "post_allocation_free_mb": stor_ev.get("post_allocation_free_mb"),
                            "target_reached": stor_ev.get("target_reached", False),
                            "bounded_pressure_applied": stor_ev.get("bounded_pressure_applied", False),
                            "limitation_reason": stor_ev.get("limitation_reason"),
                        },
                    })

            # 4. RAM constraint
            elif name == "ram_constraint":
                if not condition.requested:
                    self.condition_records.append({
                        "condition": name,
                        "requested": False,
                        "target": None,
                        "apply_status": "not_requested",
                        "verification_status": "not_applicable",
                        "cleanup_status": "not_applicable",
                        "reason": condition.reason,
                    })
                else:
                    meminfo = get_device_meminfo(self.serial, self.run_cmd)
                    target_ram = int(condition.target_value)
                    actual_ram = meminfo.get("total_ram_mb")
                    avail_ram = meminfo.get("available_ram_mb")
                    self.condition_records.append({
                        "condition": name,
                        "requested": True,
                        "target": target_ram,
                        "apply_status": "report_only",
                        "verification_status": "unsupported",
                        "cleanup_status": "not_applicable",
                        "target_ram_mb": target_ram,
                        "actual_total_ram_mb": actual_ram,
                        "actual_available_ram_mb": avail_ram,
                        "reason": condition.reason,
                    })

            # 5. CPU constraint
            elif name == "cpu_constraint":
                self.condition_records.append({
                    "condition": name,
                    "requested": False,
                    "target": None,
                    "apply_status": "not_requested",
                    "verification_status": "unsupported",
                    "cleanup_status": "not_applicable",
                    "reason": condition.reason,
                })

        return self.get_evidence()

    def cleanup_and_verify(self) -> dict[str, Any]:
        """Clean up all applied conditions and verify state restoration."""
        if self._cleaned_up:
            return self.cleanup_records
        self._cleaned_up = True

        cleanup_evidence: dict[str, Any] = {}

        # 1. Reset network if applied
        if any(
            c in self.cleanup_needed
            for c in ("network_latency", "download_bandwidth", "upload_bandwidth")
        ):
            if self._reset_network_fn:
                net_reset = self._reset_network_fn(self.serial)
            else:
                from worker.runner import reset_emulator_network_profile

                net_reset = reset_emulator_network_profile(self.serial)
            cleanup_evidence["network"] = net_reset
            status = "verified" if net_reset.get("status") == "verified" else "failed"
            for rec in self.condition_records:
                if rec["condition"] in ("network_latency", "download_bandwidth", "upload_bandwidth"):
                    rec["cleanup_status"] = status
        else:
            for rec in self.condition_records:
                if rec["condition"] in ("network_latency", "download_bandwidth", "upload_bandwidth"):
                    if rec["cleanup_status"] == "pending":
                        rec["cleanup_status"] = "not_applicable"

        # 2. Reset battery saver if applied
        if "battery_saver" in self.cleanup_needed:
            bat_reset = reset_battery_saver(self.serial, self.run_cmd)
            cleanup_evidence["battery_saver"] = bat_reset
            status = "verified" if bat_reset.get("status") == "verified" else "failed"
            for rec in self.condition_records:
                if rec["condition"] == "battery_saver":
                    rec["cleanup_status"] = status
        else:
            for rec in self.condition_records:
                if rec["condition"] == "battery_saver" and rec["cleanup_status"] == "pending":
                    rec["cleanup_status"] = "not_applicable"

        # 3. Clean up storage pressure if file was allocated
        if "storage_pressure" in self.cleanup_needed:
            stor_reset = reset_storage_pressure(self.serial, STORAGE_PRESSURE_FILE, self.run_cmd)
            cleanup_evidence["storage"] = stor_reset
            status = "verified" if stor_reset.get("status") == "verified" else "failed"
            for rec in self.condition_records:
                if rec["condition"] == "storage_pressure":
                    rec["cleanup_status"] = status
        else:
            for rec in self.condition_records:
                if rec["condition"] == "storage_pressure" and rec["cleanup_status"] == "pending":
                    rec["cleanup_status"] = "not_applicable"

        # Overall cleanup check
        cleanups_verified = all(
            ev.get("status") == "verified"
            for ev in cleanup_evidence.values()
            if isinstance(ev, dict)
        )

        self.cleanup_records = {
            "status": "verified" if cleanups_verified else "partial_or_failed",
            "verified": cleanups_verified,
            "details": cleanup_evidence,
        }
        return self.cleanup_records

    def get_evidence(self) -> dict[str, Any]:
        """Produce the structured condition_evidence report field."""
        requested_conditions = [c for c in self.condition_records if c["requested"]]
        fully_applied_verified = [
            c
            for c in requested_conditions
            if c["apply_status"] == "applied"
            and c["verification_status"] in ("verified", "control_plane_verified")
        ]
        partially_applied = [
            c
            for c in requested_conditions
            if c["apply_status"] == "partially_applied"
        ]
        preexisting_conditions = [
            c
            for c in requested_conditions
            if c["apply_status"] == "already_satisfied"
            and c["verification_status"] == "verified"
        ]
        unsupported_conditions = [
            c
            for c in requested_conditions
            if c["apply_status"] == "unsupported" or c["verification_status"] == "unsupported"
        ]
        failed_conditions = [
            c
            for c in requested_conditions
            if c["apply_status"] == "failed"
        ]
        skipped_conditions = [
            c
            for c in requested_conditions
            if c["apply_status"] == "skipped"
        ]

        if not requested_conditions:
            overall_status = "none_requested"
        elif failed_conditions:
            overall_status = "partial_failure"
        elif preexisting_conditions and len(preexisting_conditions) == len(requested_conditions):
            overall_status = "already_satisfied"
        elif (partially_applied or preexisting_conditions) and (fully_applied_verified or unsupported_conditions):
            overall_status = "partially_applied_and_verified"
        elif partially_applied and not fully_applied_verified:
            overall_status = "partially_applied"
        elif preexisting_conditions:
            overall_status = "partially_applied"
        elif unsupported_conditions and fully_applied_verified:
            overall_status = "partially_applied_and_verified"
        elif fully_applied_verified and not unsupported_conditions and not partially_applied and not skipped_conditions:
            overall_status = "applied_and_verified"
        elif unsupported_conditions and not fully_applied_verified:
            overall_status = "unsupported"
        else:
            overall_status = "unverified"

        # constraints_applied is NEVER true when complete requested persona constraints were not actually satisfied
        all_requested_fully_satisfied = (
            bool(requested_conditions)
            and len(fully_applied_verified) == len(requested_conditions)
            and not partially_applied
            and not unsupported_conditions
            and not failed_conditions
            and not skipped_conditions
        )
        constraints_applied = bool(all_requested_fully_satisfied)

        return {
            "persona_id": self.plan.persona_id,
            "target_serial": self.serial,
            "is_emulator": self.plan.is_emulator,
            "overall_status": overall_status,
            "constraints_applied": constraints_applied,
            "traffic_path_verified": False,
            "applied_conditions_count": len(fully_applied_verified),
            "partially_applied_conditions_count": len(partially_applied),
            "preexisting_conditions_count": len(preexisting_conditions),
            "conditions": self.condition_records,
            "cleanup": self.cleanup_records or {"status": "pending", "verified": False},
            "note": (
                "Control-plane verification confirms emulator environment settings were read back; "
                "it does not prove arbitrary application data-plane traffic traversed the shaped network "
                "or that the application is healthy."
            ),
        }
