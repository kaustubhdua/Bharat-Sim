#!/usr/bin/env python3
"""Read-only preflight for a dedicated BharatSim Firecracker worker host.

This command never installs packages, changes sysctls, creates namespaces, or
starts a VM. It reports whether the host meets the minimum documented gates.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Callable


def _check(name: str, ok: bool, detail: str) -> dict[str, str | bool]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def inspect_host(
    *,
    proc_root: Path = Path("/proc"),
    sys_root: Path = Path("/sys"),
    dev_root: Path = Path("/dev"),
    firecracker: str | None = None,
    jailer: str | None = None,
    machine: str | None = None,
    uid: int | None = None,
    runner: Callable = subprocess.run,
    which: Callable = shutil.which,
) -> list[dict[str, str | bool]]:
    checks: list[dict[str, str | bool]] = []
    arch = machine or platform.machine()
    checks.append(_check("architecture", arch in {"x86_64", "amd64"}, f"detected {arch}; Android emulator worker target requires x86_64"))
    kvm = dev_root / "kvm"
    try:
        mode = kvm.stat().st_mode
        accessible = os.access(kvm, os.R_OK | os.W_OK)
        checks.append(_check("kvm_device", stat.S_ISCHR(mode) and accessible, f"{kvm} must be a readable/writable character device for the worker service account"))
    except OSError:
        checks.append(_check("kvm_device", False, f"{kvm} is missing or inaccessible"))

    controllers_file = sys_root / "fs/cgroup/cgroup.controllers"
    try:
        controllers = set(controllers_file.read_text().split())
        required = {"cpu", "memory", "pids", "io"}
        missing = sorted(required - controllers)
        checks.append(_check("cgroup_v2", not missing, "available: " + ", ".join(sorted(controllers)) if not missing else "missing controllers: " + ", ".join(missing)))
    except OSError:
        checks.append(_check("cgroup_v2", False, f"cannot read {controllers_file}; unified cgroup v2 is required"))

    swaps = proc_root / "swaps"
    try:
        lines = [line for line in swaps.read_text().splitlines()[1:] if line.strip()]
        checks.append(_check("swap_disabled", not lines, "no active swap" if not lines else f"{len(lines)} active swap device(s); disable swap before accepting workloads"))
    except OSError:
        checks.append(_check("swap_disabled", False, f"cannot inspect {swaps}"))

    fc = firecracker or which("firecracker")
    jl = jailer or which("jailer")
    trusted_binaries: dict[str, bool] = {}
    for name, binary in (("firecracker", fc), ("jailer", jl)):
        trusted = False
        if binary and Path(binary).is_file() and os.access(binary, os.X_OK):
            try:
                info = Path(binary).stat()
                trusted = info.st_uid == 0 and not (info.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
            except OSError:
                trusted = False
        trusted_binaries[name] = trusted
        detail = f"{binary or name + ' not found in PATH'}; binary must be executable, root-owned and not group/world writable"
        checks.append(_check(f"{name}_binary", trusted, detail))

    versions: dict[str, str] = {}
    for name, binary in (("firecracker", fc), ("jailer", jl)):
        if not binary or not trusted_binaries[name]:
            continue
        try:
            result = runner([binary, "--version"], check=True, capture_output=True, text=True, timeout=5)
            output = (result.stdout or result.stderr or "").strip()
            match = re.search(r"v?(\d+\.\d+\.\d+)", output)
            if match:
                versions[name] = match.group(1)
            checks.append(_check(f"{name}_version", bool(match), output[:160] or "version output was empty"))
        except (OSError, subprocess.SubprocessError) as exc:
            checks.append(_check(f"{name}_version", False, f"could not read version: {type(exc).__name__}"))

    if "firecracker" in versions and "jailer" in versions:
        checks.append(_check("matching_release", versions["firecracker"] == versions["jailer"], f"firecracker={versions['firecracker']}, jailer={versions['jailer']}"))
    else:
        checks.append(_check("matching_release", False, "both version outputs are required"))

    jailer_dir = Path(jl).resolve().parent if jl and trusted_binaries["jailer"] else None
    if jailer_dir:
        try:
            info = jailer_dir.stat()
            safe = info.st_uid == 0 and not (info.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
            checks.append(_check("trusted_jailer_directory", safe, f"{jailer_dir}: owner uid={info.st_uid}, mode={stat.S_IMODE(info.st_mode):04o}; must be root-owned and not group/world writable"))
        except OSError:
            checks.append(_check("trusted_jailer_directory", False, f"cannot inspect {jailer_dir}"))
    else:
        checks.append(_check("trusted_jailer_directory", False, "jailer path unavailable"))

    checks.append(_check("operator_identity", (os.getuid() if uid is None else uid) == 0, "run preflight as root for host inspection; do not run customer workloads as root"))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--firecracker", help="explicit Firecracker binary path")
    parser.add_argument("--jailer", help="explicit matching jailer binary path")
    args = parser.parse_args()
    checks = inspect_host(firecracker=args.firecracker, jailer=args.jailer)
    passed = sum(bool(item["ok"]) for item in checks)
    failed = len(checks) - passed
    if args.json:
        print(json.dumps({"ready": failed == 0, "passed": passed, "failed": failed, "checks": checks}, indent=2))
    else:
        for item in checks:
            print(f"[{'PASS' if item['ok'] else 'BLOCK'}] {item['name']}: {item['detail']}")
        print(f"\n{passed}/{len(checks)} checks passed; {failed} blocking issue(s).")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
