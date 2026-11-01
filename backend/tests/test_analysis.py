from app.main import analyze_log_text, failure_fingerprint


def test_detects_crash_network_and_memory_signals():
    text = "\n".join([
        "FATAL EXCEPTION: main",
        "java.lang.OutOfMemoryError: Failed to allocate 1024 bytes",
        "java.net.SocketTimeoutException: timeout",
    ])
    result = analyze_log_text(text, "budget-android")
    assert {f["kind"] for f in result["findings"]} == {"crash", "oom", "network"}
    assert result["summary"]["critical"] == 2
    assert result["bharat_score"]["value"] == 30
    assert all(f["evidence"][0]["line"] > 0 for f in result["findings"])


def test_clean_logs_have_full_heuristic_score_but_are_not_proof():
    result = analyze_log_text("Activity resumed\nFrame rendered", "baseline")
    assert result["findings"] == []
    assert result["bharat_score"]["value"] == 100
    assert any("does not mean the apk was installed or executed" in x.lower() for x in result["limitations"])


def test_fingerprint_is_stable_and_normalizes_numbers():
    assert failure_fingerprint("request 123 failed") == failure_fingerprint("request 456 failed")


def test_invalid_persona_rejected():
    try:
        analyze_log_text("FATAL EXCEPTION", "unknown")
        assert False, "expected ValueError"
    except ValueError:
        pass



def test_failure_dna_groups_repeated_markers_and_preserves_context():
    result = analyze_log_text(
        "Activity resumed\njava.net.SocketTimeoutException: read timed out after 120 ms\n"
        "Retry scheduled\njava.net.SocketTimeoutException: read timed out after 240 ms",
        "edge-village",
    )
    assert result["failure_dna"]["group_count"] == 1
    assert result["failure_dna"]["total_occurrences"] == 2
    finding = result["findings"][0]
    assert finding["occurrence_count"] == 2
    assert finding["line_numbers"] == [2, 4]
    assert finding["evidence_context"][0]["line"] == 1
    assert finding["root_cause_hypothesis"]["status"] == "unconfirmed"
    assert finding["impact_priority"]["score"] > 70


def test_log_analysis_redacts_credentials_from_evidence():
    result = analyze_log_text(
        "FATAL EXCEPTION: main authorization: Bearer abc.def.ghi api_key=private-token",
        "baseline",
    )
    evidence = result["findings"][0]["evidence"][0]["text"]
    assert "abc.def.ghi" not in evidence
    assert "private-token" not in evidence
    assert "[REDACTED]" in evidence
    assert any("redacted" in item.lower() for item in result["limitations"])


def test_user_impact_is_a_relative_priority_not_a_population_claim():
    result = analyze_log_text("FATAL EXCEPTION: main", "budget-android")
    impact = result["user_impact"]
    assert impact["label"] == "Relative exposure heuristic"
    assert impact["priority_score"] == 100
    assert not any("affected users" in key for key in impact)
    assert any("not an affected-user" in item.lower() for item in impact["assumptions"])
