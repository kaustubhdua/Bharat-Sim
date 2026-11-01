"""Fail-closed fusion of independent Android worker evidence sources.

This module correlates bounded logcat markers with condition-manager readbacks,
network-control evidence, and execution steps. It never upgrades a heuristic
correlation into a confirmed root cause or an application health pass.
"""
from __future__ import annotations

import re
from typing import Any

SIGNAL_CATEGORIES = ("crash", "anr", "oom", "network", "storage")
VERIFIED_STATES = {"verified", "control_plane_verified", "applied_and_verified"}
MAX_SIGNALS = 10
MAX_EVIDENCE_PER_SIGNAL = 3
MAX_TEXT_CHARS = 400


def _short_text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _successful_step_names(report: dict[str, Any]) -> set[str]:
    steps = report.get("steps")
    if not isinstance(steps, list):
        return set()
    return {
        step.get("name")
        for step in steps
        if isinstance(step, dict)
        and isinstance(step.get("name"), str)
        and step.get("return_code") == 0
    }


def _condition_states(report: dict[str, Any]) -> dict[str, str]:
    evidence = report.get("condition_evidence")
    conditions = evidence.get("conditions") if isinstance(evidence, dict) else None
    states: dict[str, str] = {}
    if not isinstance(conditions, list):
        return states
    for item in conditions[:32]:
        if not isinstance(item, dict):
            continue
        name = item.get("condition")
        if not isinstance(name, str):
            continue
        apply_status = str(item.get("apply_status", "unknown"))
        verify_status = str(item.get("verification_status", "unknown"))
        if apply_status == "already_satisfied" and verify_status in VERIFIED_STATES:
            states[name] = "preexisting_verified"
        elif verify_status in VERIFIED_STATES:
            states[name] = "verified"
        elif apply_status == "unsupported" or verify_status == "unsupported":
            states[name] = "unsupported"
        elif apply_status in {"failed", "partial_failure"} or verify_status in {"unverified", "failed"}:
            states[name] = "unverified"
        else:
            states[name] = "not_verified"
    return states


def fuse_worker_report(report: Any) -> dict[str, Any]:
    """Return an evidence-linked, conservative synthesis for one worker report."""
    if not isinstance(report, dict):
        return {
            "schema_version": "1.0",
            "status": "INCOMPLETE",
            "review_required": True,
            "summary": "No structured Android worker report is available for evidence fusion.",
            "observations": [],
            "hypotheses": [],
            "sources": [],
            "limitations": ["A missing worker report is not evidence that the application passed."],
        }

    steps = _successful_step_names(report)
    logcat_collected = "collect_logcat" in steps
    signals = report.get("log_signals")
    signals = signals if isinstance(signals, list) else []
    normalized: dict[str, list[dict[str, Any]]] = {category: [] for category in SIGNAL_CATEGORIES}

    for signal in signals[:MAX_SIGNALS * 2]:
        if not isinstance(signal, dict):
            continue
        category = signal.get("category")
        if not isinstance(category, str) or category not in normalized:
            continue
        line = signal.get("line_number")
        line_number = line if isinstance(line, int) and line > 0 else None
        evidence_items = signal.get("evidence")
        evidence: list[dict[str, Any]] = []
        if isinstance(evidence_items, list):
            for item in evidence_items[:MAX_EVIDENCE_PER_SIGNAL]:
                if not isinstance(item, dict):
                    continue
                evidence_line = item.get("line_number")
                evidence.append({
                    "line_number": evidence_line if isinstance(evidence_line, int) and evidence_line > 0 else None,
                    "text": _short_text(item.get("text")),
                })
        normalized[category].append({
            "line_number": line_number,
            "marker": _short_text(signal.get("marker"), 160),
            "evidence": evidence,
        })

    marker_flags = {
        "crash": report.get("fatal_exception_marker") is True,
        "anr": report.get("anr_marker") is True,
        "oom": report.get("oom_marker") is True,
        "network": report.get("network_failure_marker") is True,
        "storage": report.get("storage_failure_marker") is True,
    }
    observations: list[dict[str, Any]] = []
    observed_categories: set[str] = set()
    for category in SIGNAL_CATEGORIES:
        items = normalized[category]
        observed = marker_flags[category] or bool(items)
        if observed:
            observed_categories.add(category)
        observations.append({
            "category": category,
            "status": "observed" if items else "observed_without_line_excerpt" if marker_flags[category] else "not_observed",
            "count": len(items) if items else int(marker_flags[category]),
            "evidence": items[:MAX_SIGNALS],
            "interpretation": (
                "A bounded logcat marker was observed; it identifies a symptom, not a proven cause."
                if observed
                else "No known marker was found in the captured logcat window; this is not a health pass."
            ),
        })

    condition_states = _condition_states(report)
    network = report.get("network_profile")
    network = network if isinstance(network, dict) else {}
    control_plane = network.get("control_plane")
    control_plane = control_plane if isinstance(control_plane, dict) else {}
    network_control_verified = control_plane.get("status") == "verified"
    traffic_path_verified = network.get("traffic_path_verified") is True
    storage_verified = condition_states.get("storage_pressure") == "verified"
    ram_state = condition_states.get("ram_constraint", "not_requested")

    hypotheses: list[dict[str, Any]] = []

    if "network" in observed_categories:
        corroborated = network_control_verified and traffic_path_verified
        hypotheses.append({
            "id": "network_failure_under_profile",
            "category": "network",
            "confidence": "medium" if corroborated else "low",
            "status": "unconfirmed",
            "statement": (
                "A network failure marker coincided with verified network controls and a verified fixture traffic path."
                if corroborated
                else "A network failure marker was observed, but the report does not verify both the applied network controls and the active traffic path."
            ),
            "supporting_sources": ["logcat", "network_control_plane", "network_data_plane"] if corroborated else ["logcat"] + (["network_control_plane"] if network_control_verified else []),
            "validation_steps": [
                "Repeat the same app flow under a baseline profile and the shaped profile.",
                "Compare multiple requests and preserve the exact transport and readback evidence.",
                "Inspect the app's request-level logs before attributing the symptom to network shaping.",
            ],
        })

    if "storage" in observed_categories:
        hypotheses.append({
            "id": "storage_failure_under_pressure",
            "category": "storage",
            "confidence": "medium" if storage_verified else "low",
            "status": "unconfirmed",
            "statement": (
                "A storage failure marker coincided with a verified storage-pressure condition."
                if storage_verified
                else "A storage failure marker was observed, but storage pressure was not independently verified for this run."
            ),
            "supporting_sources": ["logcat", "condition_manager"] if storage_verified else ["logcat"],
            "validation_steps": [
                "Confirm the /data free-space readback immediately before the failure.",
                "Repeat with a baseline storage budget and compare the same app action.",
                "Inspect the exact ENOSPC or storage exception context.",
            ],
        })

    if "oom" in observed_categories:
        ram_verified = ram_state == "verified"
        hypotheses.append({
            "id": "memory_pressure_and_oom",
            "category": "oom",
            "confidence": "medium" if ram_verified else "low",
            "status": "unconfirmed",
            "statement": (
                "An OOM marker coincided with a verified RAM constraint."
                if ram_verified
                else "An OOM marker was observed, but BharatSim's RAM constraint is report-only and cannot be used to attribute this failure to a simulated low-RAM condition."
            ),
            "supporting_sources": ["logcat", "condition_manager"] if ram_verified else ["logcat"],
            "validation_steps": [
                "Inspect the process and system memory telemetry around the OOM marker.",
                "Repeat on a device with an independently enforced memory limit.",
                "Compare the same flow against an unconstrained baseline.",
            ],
        })

    for category in ("crash", "anr"):
        if category in observed_categories:
            hypotheses.append({
                "id": f"{category}_symptom",
                "category": category,
                "confidence": "low",
                "status": "unconfirmed",
                "statement": f"A {category.upper()} marker was observed in logcat. The marker confirms a symptom, not the underlying root cause.",
                "supporting_sources": ["logcat"],
                "validation_steps": [
                    "Inspect the full surrounding logcat context and process state.",
                    "Reproduce the same user flow and capture a fresh trace.",
                    "Compare against a baseline device profile before attributing the symptom to a constraint.",
                ],
            })

    if observed_categories:
        corroborated_count = sum(item["confidence"] == "medium" for item in hypotheses)
        status = "CORRELATED" if corroborated_count else "OBSERVED_ONLY"
        summary = (
            "At least one symptom has independent condition and traffic evidence; all root-cause hypotheses remain unconfirmed."
            if corroborated_count
            else "Symptoms were observed, but independent evidence is insufficient to attribute them to the requested constraints."
        )
    elif logcat_collected:
        status = "NO_MARKER_OBSERVED"
        summary = "No known diagnostic markers were found in the captured logcat window. This is not proof that the app is healthy."
    else:
        status = "INCOMPLETE"
        summary = "The report does not contain a successful logcat collection step, so diagnostic coverage is incomplete."

    sources = [
        {"id": "logcat", "status": "available" if logcat_collected else "missing", "detail": "Bounded threadtime logcat capture."},
        {"id": "condition_manager", "status": "available" if isinstance(report.get("condition_evidence"), dict) else "missing", "detail": "Requested, applied, readback, and cleanup condition records."},
        {"id": "network_control_plane", "status": "verified" if network_control_verified else "partial_or_missing", "detail": "Android Emulator network control readback."},
        {"id": "network_data_plane", "status": "verified" if traffic_path_verified else "unverified", "detail": "Active app traffic path; fixture-only evidence must not be generalized to arbitrary APK traffic."},
        {"id": "execution_steps", "status": "available" if steps else "missing", "detail": "ADB step return codes and durations."},
    ]

    limitations = [
        "Correlations are deterministic heuristics, not a confirmed root-cause diagnosis.",
        "A missing marker in bounded logcat does not prove the application is healthy.",
        "A verified emulator control plane does not prove arbitrary application traffic traversed the shaped path.",
        "RAM restriction is report-only; OOM markers cannot be attributed to a simulated RAM cap.",
    ]
    report_limitations = report.get("limitations")
    if isinstance(report_limitations, list):
        for item in report_limitations[:8]:
            text = _short_text(item)
            if text and text not in limitations:
                limitations.append(text)

    return {
        "schema_version": "1.0",
        "status": status,
        "review_required": True,
        "summary": summary,
        "execution": {
            "status": _short_text(report.get("status"), 40) or "unknown",
            "logcat_collected": logcat_collected,
            "apk_sha256_valid": bool(re.fullmatch(r"[0-9a-f]{64}", str(report.get("apk_sha256", "")))),
            "successful_steps": sorted(steps),
        },
        "observations": observations,
        "hypotheses": hypotheses,
        "sources": sources,
        "verified_conditions": sorted(name for name, state in condition_states.items() if state == "verified"),
        "preexisting_conditions": sorted(name for name, state in condition_states.items() if state == "preexisting_verified"),
        "unsupported_conditions": sorted(name for name, state in condition_states.items() if state == "unsupported"),
        "limitations": limitations[:16],
    }
