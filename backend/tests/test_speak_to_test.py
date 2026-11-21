"""Speak-to-Test, scenario storage and FixProof (acceptance cases from the finale brief)."""
from __future__ import annotations

import copy
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app import testspec
from app.sarvam import SarvamNotConfigured, SarvamProviderError

client = TestClient(main.app)

HINDI = "मेरा पेमेंट ऐप धीमे नेटवर्क में पेमेंट के बाद पेंडिंग दिखा रहा है। जाँच करो कि रीट्राई करने पर डुप्लिकेट रिक्वेस्ट तो नहीं जाती।"
HINGLISH = "Mera payment app slow network mein payment karne ke baad pending dikha raha hai. Check karo ki retry karne par duplicate request toh nahi hoti."


def model_reply(**overrides):
    data = {
        "language_detected": "hi-IN", "objective": "Verify a retried payment is not charged twice.",
        "app_hint": "", "journey": "payment", "journey_description": "Pay, network slow, retry",
        "persona_id": "budget-android", "conditions": ["slow_network", "server_delay"],
        "expected_behaviour": ["Shows pending", "No duplicate charge"],
        "assertions": ["no_duplicate_charge", "honest_pending_state"], "evidence": ["ui_text", "backend_requests"],
        "matched_scenario": "upi-pending-retry", "safety_flags": [], "clarifications_needed": [],
    }
    data.update(overrides)
    return {"content": json.dumps(data, ensure_ascii=False), "request_id": "req-1", "model": "sarvam-105b",
            "latency_ms": 420, "usage": {}}


@pytest.fixture(autouse=True)
def reset_budget():
    main._SARVAM_CALLS.clear()
    yield
    main._SARVAM_CALLS.clear()


def interpret(text):
    res = client.post("/api/v1/speak/interpret", json={"text": text})
    assert res.status_code == 200, res.text
    return res.json()


def test_hindi_request_via_sarvam_maps_to_payment_scenario(monkeypatch):
    seen = {}

    def fake_chat(system, user, schema, name, *a, **k):
        seen["user"], seen["schema"] = user, schema
        return model_reply()

    monkeypatch.setattr(main, "chat_json", fake_chat)
    spec = interpret(HINDI)
    assert spec["interpreter"]["provider"] == "sarvam" and spec["interpreter"]["fallback"] is False
    assert spec["matched_scenario"] == "upi-pending-retry"
    assert spec["execution"] == {**spec["execution"], "eligible": True, "mode": "scenario", "scenario_id": "upi-pending-retry"}
    assert {a["id"] for a in spec["machine_checked_assertions"]} == {"honest_pending_state", "no_duplicate_charge", "final_state_matches_bank"}
    assert seen["schema"]["additionalProperties"] is False
    assert HINDI in seen["user"]


def test_hinglish_request_rule_fallback_when_key_missing(monkeypatch):
    def no_key(*a, **k):
        raise SarvamNotConfigured("no key")

    monkeypatch.setattr(main, "chat_json", no_key)
    spec = interpret(HINGLISH)
    assert spec["interpreter"]["fallback"] is True
    assert spec["interpreter"]["fallback_reason"] == "Sarvam is not configured"
    assert spec["language_detected"] == "hinglish"
    assert spec["journey"] == "payment"
    assert spec["matched_scenario"] == "upi-pending-retry"
    assert "no_duplicate_charge" in spec["assertions"]


def test_sarvam_timeout_falls_back(monkeypatch):
    def timeout(*a, **k):
        raise SarvamProviderError("Sarvam request failed or timed out.")

    monkeypatch.setattr(main, "chat_json", timeout)
    spec = interpret(HINGLISH)
    assert spec["interpreter"]["fallback_reason"] == "Sarvam was unavailable"


@pytest.mark.parametrize("bad", [
    "not json at all",
    json.dumps({"journey": "payment"}),
    json.dumps({**json.loads(model_reply()["content"]), "journey": "rm -rf /"}),
    json.dumps({**json.loads(model_reply()["content"]), "matched_scenario": "../../etc/passwd"}),
    json.dumps({**json.loads(model_reply()["content"]), "shell": "curl evil"}),
])
def test_invalid_model_output_is_rejected(monkeypatch, bad):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: {**model_reply(), "content": bad})
    spec = interpret(HINGLISH)
    assert spec["interpreter"]["fallback"] is True
    assert spec["interpreter"]["fallback_reason"].startswith("Sarvam output was rejected")
    assert spec["matched_scenario"] in (None, "upi-pending-retry")


def test_ambiguous_request_needs_clarification(monkeypatch):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply(
        journey="other", matched_scenario="none", assertions=[], conditions=[],
        clarifications_needed=["Which journey should be tested?"]))
    spec = interpret("app theek se test karo")
    assert spec["execution"]["eligible"] is False
    assert spec["execution"]["mode"] == "needs_clarification"
    assert spec["clarifications_needed"]


def test_unsupported_conditions_are_reported(monkeypatch):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply(
        matched_scenario="none", conditions=["cpu_throttle", "incoming_call", "slow_network"], assertions=["no_crash", "session_recovery"]))
    spec = interpret("Test my video app with CPU throttling and an incoming call on slow network")
    unsupported = {c["condition"] for c in spec["unsupported_conditions"]}
    assert unsupported == {"cpu_throttle", "incoming_call"}
    assert spec["execution"]["mode"] == "generic"
    assert spec["not_machine_verified"] == ["session_recovery"]


def test_server_delay_without_scenario_is_unsupported(monkeypatch):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply(matched_scenario="none", journey="login"))
    spec = interpret("login slow server")
    assert "server_delay" in {c["condition"] for c in spec["unsupported_conditions"]}


def test_safety_flags_block_execution(monkeypatch):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply(safety_flags=["real_money"]))
    spec = interpret("Use my real UPI account and pay real money to test")
    assert spec["execution"]["eligible"] is False and spec["execution"]["mode"] == "blocked"
    assert spec["execution"]["scenario_id"] is None


def test_sensitive_input_is_redacted_before_sarvam(monkeypatch):
    seen = {}

    def fake_chat(system, user, *a, **k):
        seen["user"] = user
        return model_reply()

    monkeypatch.setattr(main, "chat_json", fake_chat)
    text = ("payment retry test, my password=hunter2 upi ravi@okicici phone 9876543210 "
            "card 4111 1111 1111 1111 token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmn")
    spec = interpret(text)
    for secret in ("hunter2", "ravi@okicici", "9876543210", "4111 1111 1111 1111", "eyJhbGciOiJIUzI1NiJ9"):
        assert secret not in seen["user"]
        assert secret not in spec["request_text"]
    assert spec["interpreter"]["redacted_input"] is True


def test_duplicate_requests_get_same_spec_hash(monkeypatch):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply())
    a, b = interpret(HINDI), interpret(HINDI)
    assert a["spec_hash"] == b["spec_hash"]
    assert a["spec_id"] != b["spec_id"]


def test_unauthorized_user_cannot_use_ai_endpoints(monkeypatch):
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    for path, kwargs in (("/api/v1/speak/interpret", {"json": {"text": HINGLISH}}),
                         ("/api/v1/fixproof", {"json": {"original_run_id": "a" * 10, "candidate_run_id": "b" * 10}}),
                         ("/api/v1/translate/audio", {"json": {"text": "namaste"}})):
        assert client.post(path, **kwargs).status_code == 401


def test_sarvam_budget_limits_calls(monkeypatch):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply())
    monkeypatch.setattr(main, "SARVAM_CALLS_PER_10_MIN", 2)
    assert client.post("/api/v1/speak/interpret", json={"text": HINDI}).status_code == 200
    assert client.post("/api/v1/speak/interpret", json={"text": HINDI}).status_code == 200
    assert client.post("/api/v1/speak/interpret", json={"text": HINDI}).status_code == 429


def test_transcribe_without_key_is_503(monkeypatch):
    def no_key(*a, **k):
        raise SarvamNotConfigured("no key")

    monkeypatch.setattr(main, "transcribe_audio", no_key)
    res = client.post("/api/v1/speak/transcribe", files={"audio": ("v.webm", b"\x1aE\xdf\xa3" * 10, "audio/webm")})
    assert res.status_code == 503


def test_transcribe_rejects_non_audio_and_empty():
    assert client.post("/api/v1/speak/transcribe", files={"audio": ("x.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/v1/speak/transcribe", files={"audio": ("v.webm", b"", "audio/webm")}).status_code == 422


def test_scenarios_catalog_is_honest():
    items = client.get("/api/v1/scenarios").json()["items"]
    executable = [i for i in items if i["status"] == "executable"]
    assert [i["id"] for i in executable] == ["upi-pending-retry"]
    assert all(i.get("reason") for i in items if i["status"] == "planned")


# ---------------------------------------------------------------- scenario storage boundary


def test_only_allowlisted_scenario_ids_reach_the_worker():
    assert main._job_scenario_id(json.dumps({"scenario_id": "upi-pending-retry"})) == "upi-pending-retry"
    assert main._job_scenario_id(json.dumps({"scenario_id": "; rm -rf /"})) is None
    assert main._job_scenario_id("not json") is None
    with pytest.raises(HTTPException):
        main.resolve_scenario({"scenario_id": "anything-else"})
    with pytest.raises(HTTPException):
        main.resolve_scenario({"scenario_id": "upi-pending-retry", "spec": {"spec_id": "x"}})
    with pytest.raises(HTTPException):
        main.resolve_scenario({"scenario_id": "upi-pending-retry", "extra": "field"})


def test_saved_spec_round_trip(monkeypatch):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply())
    spec = interpret(HINDI)
    stored = json.loads(main.resolve_scenario({"scenario_id": "upi-pending-retry", "spec": spec}))
    assert stored["scenario_id"] == "upi-pending-retry"
    assert stored["spec_hash"] == spec["spec_hash"]
    assert "interpreter" not in stored["spec"]
    assert main.resolve_scenario(None) is None


# ---------------------------------------------------------------- explanations


def test_explain_requires_a_report(monkeypatch):
    import sqlite3
    from contextlib import contextmanager
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE runs (id TEXT, result_json TEXT, owner_id TEXT)")
    conn.execute("INSERT INTO runs VALUES ('r-empty', NULL, NULL)")

    @contextmanager
    def fake_db():
        yield conn

    monkeypatch.setattr(main, "db", fake_db)
    assert client.post("/api/v1/runs/r-empty/explain", json={"audience": "public"}).status_code == 409
    assert client.post("/api/v1/runs/missing/explain", json={}).status_code == 404


def test_evidence_items_carry_no_raw_logcat():
    report = {"readiness": {"overall": 40, "status": "fail", "categories": {}},
              "constrained": {"findings": [{"category": "crash", "severity": "critical", "message": "crashed",
                                            "evidence": ["E AndroidRuntime: token=abc123 FATAL"]}], "signals": {"crashes": 1}},
              "scenario": scenario_block(False, False, True)}
    items = main.run_evidence_items(report)
    joined = json.dumps(items)
    assert "AndroidRuntime" not in joined and "abc123" not in joined
    assert any(i["id"] == "E-no_duplicate_charge" for i in items)


# ---------------------------------------------------------------- FixProof


def scenario_block(dup_ok: bool, pending_ok: bool, final_ok: bool, status: str = "completed") -> dict:
    return {"id": "upi-pending-retry", "title": "UPI", "status": status, "verdict": "pass" if dup_ok and pending_ok and final_ok else "fail",
            "assertions": [
                {"id": "no_duplicate_charge", "label": "no dup", "passed": dup_ok, "observed": "x"},
                {"id": "honest_pending_state", "label": "pending", "passed": pending_ok, "observed": "y"},
                {"id": "final_state_matches_bank", "label": "final", "passed": final_ok, "observed": "z"},
            ]}


def run(rid, sha, scen, status="completed", crashes=0, persona="budget-android"):
    return {"id": rid, "status": status, "apk_sha256": sha,
            "result": {"scenario": scen, "constrained": {"signals": {"crashes": crashes}}} if scen is not None else {},
            "scenario": {"scenario_id": "upi-pending-retry", "spec_hash": "aaaaaaaaaaaaaaaa", "spec": {"persona_id": persona}}}


ORIGINAL = run("o", "sha-original", scenario_block(False, False, True))


def test_fixproof_fixed_and_verified():
    v = testspec.fixproof(ORIGINAL, run("c", "sha-fixed", scenario_block(True, True, True)))
    assert v["verdict"] == "FIXED_AND_VERIFIED"


def test_fixproof_still_failing():
    v = testspec.fixproof(ORIGINAL, run("c", "sha-fixed", scenario_block(True, False, True)))
    assert v["verdict"] == "STILL_FAILING"


def test_fixproof_regression():
    v = testspec.fixproof(ORIGINAL, run("c", "sha-fixed", scenario_block(True, True, False)))
    assert v["verdict"] == "REGRESSION_INTRODUCED"


def test_fixproof_different_failure():
    v = testspec.fixproof(ORIGINAL, run("c", "sha-fixed", scenario_block(True, True, True), crashes=2))
    assert v["verdict"] == "DIFFERENT_FAILURE"


def test_fixproof_not_reproduced():
    good = run("o", "sha-original", scenario_block(True, True, True))
    v = testspec.fixproof(good, run("c", "sha-fixed", scenario_block(True, True, True)))
    assert v["verdict"] == "NOT_REPRODUCED"


@pytest.mark.parametrize("candidate", [
    run("c", "sha-original", scenario_block(True, True, True)),                       # same build
    run("c", "sha-fixed", scenario_block(True, True, True), status="queued"),           # worker has not run it
    run("c", "sha-fixed", None),                                                       # no scenario executed
    run("c", "sha-fixed", scenario_block(True, True, True, status="blocked")),          # assertions not executed
    run("c", "sha-fixed", scenario_block(True, True, True), persona="edge-village"),  # different persona
])
def test_fixproof_never_verifies_an_unexecuted_or_incomparable_fix(candidate):
    v = testspec.fixproof(ORIGINAL, candidate)
    assert v["verdict"] == "VERIFICATION_BLOCKED"


def test_fixproof_unsupported():
    v = testspec.fixproof(ORIGINAL, run("c", "sha-fixed", {**scenario_block(True, True, True), "status": "unsupported"}))
    assert v["verdict"] == "UNSUPPORTED"


def test_fixproof_endpoint_is_owner_scoped(monkeypatch):
    import sqlite3
    from contextlib import contextmanager
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE runs (id TEXT, status TEXT, apk_sha256 TEXT, result_json TEXT, scenario_json TEXT, owner_id TEXT)")
    for r, owner in ((ORIGINAL, "a"), (run("c", "sha-fixed", scenario_block(True, True, True)), "b")):
        conn.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (r["id"], r["status"], r["apk_sha256"],
                     json.dumps(r["result"]), json.dumps(r["scenario"]), owner))

    @contextmanager
    def fake_db():
        yield conn

    monkeypatch.setattr(main, "db", fake_db)
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "verify_supabase_access_token", lambda token: "a")
    res = client.post("/api/v1/fixproof", json={"original_run_id": "o" * 1 + "-original", "candidate_run_id": "c-candidate1"},
                      headers={"Authorization": "Bearer t"})
    assert res.status_code == 404
    conn.execute("UPDATE runs SET owner_id='a'")
    conn.execute("UPDATE runs SET id='o-original' WHERE id='o'")
    conn.execute("UPDATE runs SET id='c-candidate1' WHERE id='c'")
    res = client.post("/api/v1/fixproof", json={"original_run_id": "o-original", "candidate_run_id": "c-candidate1"},
                      headers={"Authorization": "Bearer t"})
    assert res.status_code == 200 and res.json()["verdict"] == "FIXED_AND_VERIFIED"


def test_rule_based_spec_is_valid_for_odd_inputs():
    for text in ("", "????", "a" * 1000, HINDI, "form submit karte waqt network gaya"):
        spec = testspec.rule_based_spec(text or "x")
        built = testspec.build_spec(spec, text, {"provider": "rule-based fallback"})
        assert built["execution"]["mode"] in {"scenario", "generic", "needs_clarification", "blocked"}


def test_scenario_spec_identity_ignores_model_wording(monkeypatch):
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply(conditions=["slow_network"], journey="order_tracking",
                                                                       clarifications_needed=["Which journey?"]))
    a = interpret(HINGLISH)
    monkeypatch.setattr(main, "chat_json", lambda *a, **k: model_reply(conditions=["server_delay", "network_drop"]))
    b = interpret(HINGLISH)
    assert a["spec_hash"] == b["spec_hash"]
    assert a["journey"] == "payment" and a["clarifications_needed"] == []


def test_fenced_model_json_is_accepted():
    content = "```json" + chr(10) + model_reply()["content"] + chr(10) + "```"
    assert testspec.parse_model_output(content).matched_scenario == "upi-pending-retry"


def test_fixproof_verdict_is_consistent_across_repeated_candidate_runs():
    verdicts = []
    for attempt in range(3):
        original = run(f"original-{attempt}", "sha-original", scenario_block(False, False, True))
        candidate = run(f"candidate-{attempt}", "sha-fixed", scenario_block(True, True, True))
        verdicts.append(testspec.fixproof(original, candidate)["verdict"])
    assert verdicts == ["FIXED_AND_VERIFIED"] * 3
