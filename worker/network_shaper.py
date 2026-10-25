#!/usr/bin/env python3
"""Apply/verify/clear outbound Linux netem shaping on a dedicated test veth only.

This intentionally refuses arbitrary host interfaces. Create a disposable
network namespace and a dedicated interface named veth-bs-<suffix> first.
The script shapes egress on that interface only; it does not claim to shape
Android emulator traffic unless that traffic is routed through the interface.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys


IFACE_RE = re.compile(r"^veth-bs-[a-z0-9]{1,12}$")


def parse_netem_parameters(output: str) -> dict[str, float | None]:
    """Parse observed tc text; absent settings are represented as zero only when qdisc exists."""
    delay = re.search(r"\bdelay\s+([0-9.]+)(ns|us|ms|s)\b(?:\s+([0-9.]+)(ns|us|ms|s)\b)?", output)
    loss = re.search(r"\bloss\s+([0-9.]+)%", output)
    rate = re.search(r"\brate\s+([0-9.]+)(bit|Kbit|Mbit|Gbit)\b", output)
    time_scale = {"ns": 0.000001, "us": 0.001, "ms": 1.0, "s": 1000.0}
    rate_scale = {"bit": 0.001, "Kbit": 1.0, "Mbit": 1000.0, "Gbit": 1000000.0}
    has_netem = "netem" in output
    return {
        "latency_ms": float(delay.group(1)) * time_scale[delay.group(2)] if delay else (0.0 if has_netem else None),
        "jitter_ms": float(delay.group(3)) * time_scale[delay.group(4)] if delay and delay.group(3) else (0.0 if has_netem else None),
        "loss_pct": float(loss.group(1)) if loss else (0.0 if has_netem else None),
        "rate_kbit": float(rate.group(1)) * rate_scale[rate.group(2)] if rate else None,
    }


def parameters_match(observed: dict[str, float | None], requested: dict[str, float]) -> bool:
    """Use small tolerances for tc's unit conversion/formatting; missing values never match."""
    tolerances = {"latency_ms": 0.1, "jitter_ms": 0.1, "loss_pct": 0.001, "rate_kbit": 0.1}
    return all(
        observed.get(key) is not None and abs(float(observed[key]) - value) <= tolerances[key]
        for key, value in requested.items()
    )


def run(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("apply", "verify", "clear"))
    parser.add_argument("--interface", required=True, help="dedicated veth named veth-bs-<suffix>")
    parser.add_argument("--latency-ms", type=float, default=180)
    parser.add_argument("--jitter-ms", type=float, default=30)
    parser.add_argument("--loss-pct", type=float, default=2)
    parser.add_argument("--rate-kbit", type=int, default=1200)
    args = parser.parse_args()

    if not IFACE_RE.fullmatch(args.interface):
        parser.error("refusing arbitrary interfaces; use a dedicated veth-bs-<suffix> test interface")
    if os.getenv("BHARATSIM_ENABLE_NETEM") != "true":
        parser.error("set BHARATSIM_ENABLE_NETEM=true only in an isolated test network namespace")
    if os.geteuid() != 0:
        parser.error("tc shaping requires root; run only inside the isolated test network namespace")
    if shutil.which("tc") is None or shutil.which("ip") is None:
        parser.error("iproute2 tools 'ip' and 'tc' must be installed")
    if args.latency_ms < 0 or args.latency_ms > 5000:
        parser.error("--latency-ms must be between 0 and 5000")
    if args.jitter_ms < 0 or args.jitter_ms > 2000:
        parser.error("--jitter-ms must be between 0 and 2000")
    if args.latency_ms == 0 and args.jitter_ms > 0:
        parser.error("--jitter-ms requires a positive --latency-ms so the requested profile can be applied")
    if not 0 <= args.loss_pct <= 30:
        parser.error("--loss-pct must be between 0 and 30")
    if not 16 <= args.rate_kbit <= 1000000:
        parser.error("--rate-kbit must be between 16 and 1000000")

    link = run(["ip", "link", "show", "dev", args.interface])
    if link.returncode != 0:
        parser.error("dedicated test interface does not exist")

    if args.action == "apply":
        command = ["tc", "qdisc", "replace", "dev", args.interface, "root", "netem"]
        if args.latency_ms > 0:
            command += ["delay", f"{args.latency_ms:g}ms", f"{args.jitter_ms:g}ms"]
        if args.loss_pct > 0:
            command += ["loss", f"{args.loss_pct:g}%"]
        command += ["rate", f"{args.rate_kbit}kbit"]
        applied = run(command)
        if applied.returncode != 0:
            print(json.dumps({"status": "apply_failed", "stderr": applied.stderr[-1500:]}))
            return 1

    if args.action == "clear":
        cleared = run(["tc", "qdisc", "del", "dev", args.interface, "root"])
        if cleared.returncode != 0:
            print(json.dumps({"status": "clear_failed", "stderr": cleared.stderr[-1500:]}))
            return 1

    measured = run(["tc", "-s", "qdisc", "show", "dev", args.interface])
    if measured.returncode != 0:
        print(json.dumps({"status": "verify_failed", "stderr": measured.stderr[-1500:]}))
        return 1
    output = measured.stdout.strip()
    has_netem = "netem" in output
    expected = args.action != "clear"
    matched = (has_netem == expected)
    requested = {"latency_ms": args.latency_ms, "jitter_ms": args.jitter_ms, "loss_pct": args.loss_pct, "rate_kbit": float(args.rate_kbit)} if args.action == "apply" else None
    observed = parse_netem_parameters(output) if has_netem else None
    parameters_verified = parameters_match(observed, requested) if observed is not None and requested is not None else None
    if not matched:
        status = "verification_mismatch"
    elif args.action == "apply" and parameters_verified is True:
        status = "parameters_match"
    elif args.action == "apply":
        status = "parameters_unverified" if observed is None or any(v is None for v in observed.values()) else "parameter_mismatch"
    else:
        status = "qdisc_present" if has_netem else "qdisc_absent"
    print(json.dumps({
        "status": status,
        "action": args.action,
        "interface": args.interface,
        "scope": "outbound interface traffic only",
        "requested": requested,
        "observed_parameters": observed,
        "observed_qdisc": output,
        "netem_present": has_netem,
        "parameters_verified": parameters_verified,
        "verification_scope": "Apply parses the qdisc parameters reported by tc and compares them to requested values. This still does not prove test-device traffic traverses this interface.",
        "warning": "Verify routing and a known endpoint independently; qdisc configuration is not end-to-end traffic evidence.",
    }, indent=2))
    return 0 if matched and (args.action != "apply" or parameters_verified is True) else 2


if __name__ == "__main__":
    sys.exit(main())
