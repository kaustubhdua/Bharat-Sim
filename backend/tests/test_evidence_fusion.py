import json

from fastapi.testclient import TestClient

from app import main
from app.evidence_fusion import fuse_worker_report


def base_report():
    return {
        "status": "completed",
        "apk_sha256": "a" * 64,
        "log_signals": [],
        "steps": [
            {"name": "install_apk", "return_code": 0},
            {"name": "launch_app", "return_code": 0},
            {"name": "collect_logcat", "return_code": 0},
        ],
        "limitations": [],
    }


def signal(category, marker):
    return {
        "category": category,
        "line_number": 42,
        "marker": marker,
        "evidence": [{"line_number": 41, "text": "observed test evidence"}],
    }


def test_missing_report_is_incomplete_and_requires_review():
    result = fuse_worker_report(None)

    assert result["status"] == "INCOMPLETE"
    assert result["review_required"] is True
    assert result["hypotheses"] == []


def test_empty_successful_logcat_is_not_reported_as_a_health_pass():
    result = fuse_worker_report(base_report())

    assert result["status"] == "NO_MARKER_OBSERVED"
    assert result["execution"]["logcat_collected"] is True
    assert "not proof" in result["summary"].lower()
    assert result["review_required"] is True


def test_network_marker_without_verified_traffic_path_stays_low_confidence():
    report = base_report()
    report["network_failure_marker"] = True
    report["log_signals"] = [signal("network", "SocketTimeoutException")]
    report["network_profile"] = {
        "traffic_path_verified": False,
        "control_plane": {"status": "verified"},
    }

    result = fuse_worker_report(report)

    assert result["status"] == "OBSERVED_ONLY"
    hypothesis = result["hypotheses"][0]
    assert hypothesis["confidence"] == "low"
    assert hypothesis["status"] == "unconfirmed"
    assert "active traffic path" in hypothesis["statement"]


def test_network_marker_with_control_and_traffic_readback_is_correlated_not_confirmed():
    report = base_report()
    report["network_failure_marker"] = True
    report["log_signals"] = [signal("network", "SocketTimeoutException")]
    report["network_profile"] = {
        "traffic_path_verified": True,
        "control_plane": {"status": "verified"},
    }

    result = fuse_worker_report(report)

    assert result["status"] == "CORRELATED"
    assert result["hypotheses"][0]["confidence"] == "medium"
    assert result["hypotheses"][0]["status"] == "unconfirmed"
    assert result["review_required"] is True


def test_storage_failure_is_correlated_only_when_storage_pressure_is_verified():
    report = base_report()
    report["storage_failure_marker"] = True
    report["log_signals"] = [signal("storage", "ENOSPC")]
    report["condition_evidence"] = {
        "conditions": [{
            "condition": "storage_pressure",
            "apply_status": "applied",
            "verification_status": "verified",
        }]
    }

    result = fuse_worker_report(report)

    assert result["status"] == "CORRELATED"
    assert result["hypotheses"][0]["confidence"] == "medium"
    assert "condition_manager" in result["hypotheses"][0]["supporting_sources"]


def test_oom_is_not_attributed_to_report_only_ram_constraint():
    report = base_report()
    report["oom_marker"] = True
    report["log_signals"] = [signal("oom", "OutOfMemoryError")]
    report["condition_evidence"] = {
        "conditions": [{
            "condition": "ram_constraint",
            "apply_status": "report_only",
            "verification_status": "report_only",
        }]
    }

    result = fuse_worker_report(report)

    assert result["status"] == "OBSERVED_ONLY"
    assert result["hypotheses"][0]["confidence"] == "low"
    assert "report-only" in result["hypotheses"][0]["statement"]


def test_untrusted_log_evidence_is_bounded_before_returning_to_dashboard():
    report = base_report()
    report["log_signals"] = [{
        "category": "crash",
        "line_number": 5,
        "marker": "x" * 1000,
        "evidence": [{"line_number": 5, "text": "y" * 5000}],
    }]

    result = fuse_worker_report(report)
    evidence = result["observations"][0]["evidence"][0]

    assert len(evidence["marker"]) == 160
    assert len(evidence["evidence"][0]["text"]) == 400

def test_run_detail_exposes_derived_diagnostics_without_mutating_saved_worker_report(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "evidence-fusion.sqlite3")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    main.init_db()
    report = base_report()

    with main.db() as conn:
        conn.execute(
            "INSERT INTO runs(id,created_at,status,apk_name,apk_sha256,persona_id,result_json,error,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("evidence-fusion-run", main.utcnow(), "completed", "test.apk", "a" * 64, "budget-android", json.dumps(report), None, main.utcnow()),
        )

    response = TestClient(main.app).get("/api/v1/runs/evidence-fusion-run")

    assert response.status_code == 200
    assert response.json()["result"]["diagnostics"]["status"] == "NO_MARKER_OBSERVED"
    with main.db() as conn:
        saved = conn.execute("SELECT result_json FROM runs WHERE id=?", ("evidence-fusion-run",)).fetchone()
    assert "diagnostics" not in json.loads(saved["result_json"])


def test_report_export_hashes_original_report_and_derived_diagnostics_separately(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "evidence-export.sqlite3")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    main.init_db()
    report = base_report()
    report["log_signals"] = [signal("crash", "FATAL EXCEPTION")]

    with main.db() as conn:
        conn.execute(
            "INSERT INTO runs(id,created_at,status,apk_name,apk_sha256,persona_id,result_json,error,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("evidence-export-run", main.utcnow(), "completed", "test.apk", "a" * 64, "budget-android", json.dumps(report), None, main.utcnow()),
        )

    response = TestClient(main.app).get("/api/v1/runs/evidence-export-run/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["diagnostics"]["status"] == "OBSERVED_ONLY"
    assert payload["integrity"]["report_sha256"]
    assert payload["integrity"]["diagnostics_sha256"]
    assert "diagnostics" not in payload["report"]

def test_malformed_signal_category_is_ignored_without_crashing():
    report = base_report()
    report["log_signals"] = [
        {"category": {"unexpected": "object"}, "line_number": 1, "marker": "bad", "evidence": []},
        signal("crash", "FATAL EXCEPTION"),
    ]

    result = fuse_worker_report(report)

    assert result["status"] == "OBSERVED_ONLY"
    assert result["observations"][0]["count"] == 1


def test_string_marker_flag_does_not_count_as_observed_boolean():
    report = base_report()
    report["fatal_exception_marker"] = "false"

    result = fuse_worker_report(report)

    assert result["status"] == "NO_MARKER_OBSERVED"


def test_preexisting_storage_state_is_not_misreported_as_applied_pressure():
    report = base_report()
    report["storage_failure_marker"] = True
    report["log_signals"] = [signal("storage", "ENOSPC")]
    report["condition_evidence"] = {
        "conditions": [{
            "condition": "storage_pressure",
            "apply_status": "already_satisfied",
            "verification_status": "verified",
        }]
    }

    result = fuse_worker_report(report)

    assert result["status"] == "OBSERVED_ONLY"
    assert result["hypotheses"][0]["confidence"] == "low"
    assert result["preexisting_conditions"] == ["storage_pressure"]
    assert result["verified_conditions"] == []
