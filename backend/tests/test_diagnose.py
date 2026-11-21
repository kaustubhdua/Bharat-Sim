"""Generic Speak-to-Test for any APK: conditions -> emulator persona, reproduction check, diagnosis."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import main, testspec

client = TestClient(main.app)


def report(signals=None, findings=None, cold=900, base_cold=850, jank=10, base_jank=8, drop=None, status="completed", installed=True):
    cons = {"label": "Your reported conditions", "installed": installed, "signals": {"crashes": 0, "anrs": 0, "ooms": 0,
            "network_errors": 0, "storage_errors": 0, **(signals or {})}, "findings": findings or [],
            "cold_start_ms_median": cold, "frames": {"jank_percent": jank}}
    if drop:
        cons["drop"] = drop
    return {"status": status, "engine": "bharatsim-engine-2.0", "readiness": {"overall": 70, "status": "warn", "categories": {}},
            "constrained": cons, "baseline": {"label": "Baseline", "installed": True, "signals": {}, "findings": [],
            "cold_start_ms_median": base_cold, "frames": {"jank_percent": base_jank}}, "anomalies": []}


CRASH_FINDING = [{"category": "crash", "severity": "critical", "message": "The app crashed 1 time(s).",
                  "evidence": ["E AndroidRuntime: FATAL EXCEPTION: main token=supersecret123", "java.lang.NullPointerException at Feed.load"]}]


@pytest.mark.parametrize("symptom,rep,verdict", [
    ("crash", report({"crashes": 1}, CRASH_FINDING), "REPRODUCED"),
    ("crash", report(), "NOT_REPRODUCED"),
    ("freeze", report({"anrs": 2}), "REPRODUCED"),
    ("out_of_memory", report(), "NOT_REPRODUCED"),
    ("network_failure", report({"network_errors": 3}), "REPRODUCED"),
    ("network_failure", report(drop={"seconds": 15, "behaviour": "crashed or closed"}), "REPRODUCED"),
    ("storage_error", report({"storage_errors": 1}), "REPRODUCED"),
    ("slow_start", report(cold=2600, base_cold=900), "REPRODUCED"),
    ("slow_start", report(cold=950, base_cold=900), "NOT_REPRODUCED"),
    ("ui_jank", report(jank=60, base_jank=12), "REPRODUCED"),
    ("ui_jank", report(jank=15, base_jank=12), "NOT_REPRODUCED"),
    ("wrong_result", report(), "CANNOT_CHECK"),
    ("crash", report(status="failed", installed=False), "BLOCKED"),
    ("crash", None, "BLOCKED"),
])
def test_reproduction_verdicts(symptom, rep, verdict):
    assert testspec.check_reproduction(symptom, rep)["verdict"] == verdict


def test_reproduction_evidence_is_redacted_and_says_only_under_conditions():
    r = testspec.check_reproduction("crash", report({"crashes": 1}, CRASH_FINDING))
    joined = json.dumps(r)
    assert "supersecret123" not in joined
    assert "only under your conditions" in r["summary"]


def test_conditions_become_an_emulator_persona():
    p = testspec.custom_persona_for(["slow_network", "network_drop", "low_storage", "battery_saver", "cpu_throttle"])
    assert p["down_kbps"] == 256 and p["drop_seconds"] == 15 and p["free_storage_mb"] == 300 and p["battery_saver"] is True
    main.CustomPersona.model_validate(p).to_profile()  # the worker accepts it
    assert testspec.custom_persona_for(["cpu_throttle", "incoming_call"]) is None
    assert testspec.custom_persona_for([]) is None


def model_reply(**over):
    data = {"language_detected": "hinglish", "objective": "Check the app does not crash on slow network.", "app_hint": "",
            "journey": "content_browsing", "journey_description": "", "persona_id": "budget-android",
            "conditions": ["slow_network"], "expected_behaviour": [], "assertions": ["no_crash"], "evidence": ["logcat"],
            "matched_scenario": "none", "safety_flags": [], "clarifications_needed": [], "symptom": "crash"}
    data.update(over)
    return {"content": json.dumps(data), "request_id": "r1", "model": "sarvam-105b", "latency_ms": 500, "usage": {}}


def test_generic_spec_runs_any_apk_with_custom_persona(monkeypatch):
    main._SARVAM_CALLS.clear()
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply())
    spec = client.post("/api/v1/speak/interpret", json={"text": "Meri news app slow network par band ho jati hai, kyun?"}).json()
    assert spec["execution"]["mode"] == "generic" and spec["execution"]["eligible"] is True
    assert spec["execution"]["persona_id"] == "custom" and spec["execution"]["custom_persona"]["down_kbps"] == 256
    assert spec["symptom"] == "crash" and spec["symptom_checkable"] is True
    stored = json.loads(main.resolve_scenario({"scenario_id": None, "spec": {**spec, "persona_id": "custom"}}))
    assert stored["spec"]["symptom"] == "crash"


def fake_db(rows):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE runs (id TEXT, status TEXT, result_json TEXT, scenario_json TEXT, owner_id TEXT)")
    conn.executemany("INSERT INTO runs VALUES (?,?,?,?,?)", rows)

    @contextmanager
    def db():
        yield conn
    return db


SPEC = json.dumps({"scenario_id": None, "spec": {"symptom": "crash", "request_text": "App crashes on slow network"}})


def test_diagnose_reproduced_crash_cites_evidence(monkeypatch):
    main._SARVAM_CALLS.clear()
    monkeypatch.setattr(main, "db", fake_db([("r1", "completed", json.dumps(report({"crashes": 1}, CRASH_FINDING)), SPEC, None)]))
    seen = {}

    def fake_chat(system, user, schema, name, *a, **k):
        seen["user"] = user
        return {"content": json.dumps({"why": "A NullPointerException in Feed.load crashes the app when the feed is slow.",
                                       "fix_steps": ["Null-check the feed response", "Show an offline state"],
                                       "code_hint": "val items = response?.items ?: emptyList()", "confidence": "medium",
                                       "evidence_ids": ["R-1", "R-3"]}), "request_id": "q", "model": "sarvam-105b", "latency_ms": 700}

    monkeypatch.setattr(main, "chat_json", fake_chat)
    res = client.post("/api/v1/runs/r1/diagnose", json={"language_code": "en-IN"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reproduction"]["verdict"] == "REPRODUCED"
    assert body["diagnosis"]["fix_steps"] and body["cited_evidence"]
    assert "supersecret123" not in seen["user"]


def test_diagnose_rejects_uncited_or_running(monkeypatch):
    main._SARVAM_CALLS.clear()
    monkeypatch.setattr(main, "db", fake_db([("r1", "completed", json.dumps(report({"crashes": 1}, CRASH_FINDING)), SPEC, None),
                                             ("r2", "leased", None, SPEC, None)]))
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: {"content": json.dumps({"why": "made up", "fix_steps": [], "code_hint": "",
                        "confidence": "high", "evidence_ids": ["X-9"]}), "request_id": "q", "model": "m", "latency_ms": 1})
    assert client.post("/api/v1/runs/r1/diagnose", json={}).status_code == 502
    assert client.post("/api/v1/runs/r2/diagnose", json={}).status_code == 409
    assert client.post("/api/v1/runs/nope/diagnose", json={}).status_code == 404


def test_diagnose_blocked_run_skips_sarvam(monkeypatch):
    main._SARVAM_CALLS.clear()
    monkeypatch.setattr(main, "db", fake_db([("r3", "failed", json.dumps(report(status="failed", installed=False)), SPEC, None)]))

    def boom(*a, **k):
        raise AssertionError("Sarvam must not be called for a blocked run")

    monkeypatch.setattr(main, "chat_json", boom)
    body = client.post("/api/v1/runs/r3/diagnose", json={}).json()
    assert body["reproduction"]["verdict"] == "BLOCKED" and body["diagnosis"] is None


def test_diagnose_any_run_with_typed_problem(monkeypatch):
    main._SARVAM_CALLS.clear()
    monkeypatch.setattr(main, "db", fake_db([("r4", "completed", json.dumps(report(cold=2600, base_cold=900)), None, None)]))
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: {"content": json.dumps({"why": "Cold start is slow.", "fix_steps": ["Defer init"],
                        "code_hint": "", "confidence": "medium", "evidence_ids": ["R-1"]}), "request_id": "q", "model": "m", "latency_ms": 1})
    body = client.post("/api/v1/runs/r4/diagnose", json={"problem": "app is slow to open, startup takes long"}).json()
    assert body["reproduction"]["symptom"] == "slow_start" and body["reproduction"]["verdict"] == "REPRODUCED"
    assert client.post("/api/v1/runs/r4/diagnose", json={}).status_code == 422


def test_diagnose_requires_sign_in(monkeypatch):
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    assert client.post("/api/v1/runs/r1/diagnose", json={}).status_code == 401


HINGLISH_CRASH = "Meri app khulte hi band ho jati hai. Kyun ho raha hai aur kaise fix karun?"


def test_typed_problem_is_classified_by_sarvam(monkeypatch):
    main._SARVAM_CALLS.clear()
    monkeypatch.setattr(main, "db", fake_db([("r5", "completed", json.dumps(report({"crashes": 5}, CRASH_FINDING)), None, None)]))
    calls = []

    def fake_chat(system, user, schema, name, *a, **k):
        calls.append(name)
        if name == "bharatsim_test_spec":
            return model_reply(symptom="crash", conditions=[])
        return {"content": json.dumps({"why": "Main-thread exception at startup.", "fix_steps": ["Catch it"], "code_hint": "",
                                       "confidence": "medium", "evidence_ids": ["R-1"]}), "request_id": "q", "model": "m", "latency_ms": 1}

    monkeypatch.setattr(main, "chat_json", fake_chat)
    body = client.post("/api/v1/runs/r5/diagnose", json={"problem": HINGLISH_CRASH}).json()
    assert calls == ["bharatsim_test_spec", "bharatsim_diagnosis"]
    assert body["reproduction"]["symptom"] == "crash" and body["reproduction"]["verdict"] == "REPRODUCED"
    assert body["reproduction"]["symptom_source"] == "sarvam"


def test_keyword_fallback_recognises_hinglish_crash():
    assert testspec.rule_based_spec(HINGLISH_CRASH).symptom == "crash"
    assert testspec.rule_based_spec("app khulte hi close ho jata hai").symptom == "crash"
