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
