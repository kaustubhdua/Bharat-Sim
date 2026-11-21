"""Tests for ML Failure Classification, Anomaly Detection, Sarvam Audio, and Evaluator Scenarios."""
from __future__ import annotations

import pytest
import json
import sqlite3
from contextlib import contextmanager

from fastapi import HTTPException
from starlette.requests import Request

from backend.app import main as main_module
from backend.app.main import CompareRunsRequest
from fastapi.testclient import TestClient

from backend.app.anomaly_detector import detect_regressions
from backend.app.evaluator_scenarios import get_all_scenarios, get_scenario_by_id
from backend.app.main import app
from backend.app.ml_classifier import classify_log_snippet, classify_logcat_stream
from backend.app.sarvam import generate_speech_audio, explain_failure_with_sarvam


@pytest.fixture
def client():
    return TestClient(app)


def test_ml_classifier_individual_snippets():
    crash_res = classify_log_snippet("FATAL EXCEPTION: main java.lang.NullPointerException")
    assert crash_res["category"] == "crash"
    assert crash_res["is_failure"] is True
    assert crash_res["confidence"] > 0.5

    anr_res = classify_log_snippet("ANR in com.bharat.app: Input dispatching timed out")
    assert anr_res["category"] == "anr"
    assert anr_res["is_failure"] is True

    oom_res = classify_log_snippet("OutOfMemoryError: Failed to allocate a 52428816 byte allocation")
    assert oom_res["category"] == "oom"
    assert oom_res["is_failure"] is True

    net_res = classify_log_snippet("java.net.SocketTimeoutException: Connection timed out")
    assert net_res["category"] == "network"
    assert net_res["is_failure"] is True

    storage_res = classify_log_snippet("java.io.IOException: write failed: ENOSPC (No space left on device)")
    assert storage_res["category"] == "storage"
    assert storage_res["is_failure"] is True

    normal_res = classify_log_snippet("I/ChatAdapter: Rendered 25 messages in RecyclerView in 14ms")
    assert normal_res["category"] == "normal"
    assert normal_res["is_failure"] is False


def test_ml_classifier_stream():
    sample_log = """
    ActivityTaskManager: START u0 {cmp=com.bharat.app/.MainActivity}
    Choreographer: Skipped 3 frames!
    java.net.SocketTimeoutException: failed to connect to api.bharatsim.io after 15000ms
    D/Lifecycle: Activity onResume called
    lowmemorykiller: Killing 'com.bharat.app' to free 48210kB because system is low on memory
    """
    matches = classify_logcat_stream(sample_log)
    categories = [m["category"] for m in matches]
    assert "network" in categories
    assert "oom" in categories


def test_anomaly_detector_regressions():
    baseline = {
        "cold_start_ms": 650,
        "jank_percentage": 4.0,
        "peak_memory_mb": 85,
        "network_latency_ms": 30,
    }
    constrained = {
        "cold_start_ms": 2900,  # +2250ms -> warning/critical
        "jank_percentage": 36.0,  # +32% -> critical
        "peak_memory_mb": 290,  # +205MB -> warning
        "network_latency_ms": 480,
    }
    result = detect_regressions(baseline, constrained)
    assert result["regression_count"] >= 2
    assert 0 <= result["anomaly_score"] <= 100
    memory_anomaly = next(item for item in result["anomalies"] if item["metric"] == "peak_memory_mb")
    assert memory_anomaly["delta"] == 205
    metrics = [a["metric"] for a in result["anomalies"]]
    assert "cold_start_ms" in metrics
    assert "jank_percentage" in metrics


def test_sarvam_tts_audio_generation():
    audio_data = generate_speech_audio("सावधान: यह ऍप क्रैश हो रहा है।", "hi-IN")
    assert "audio_base64" in audio_data
    assert len(audio_data["audio_base64"]) > 100
    assert audio_data["format"] == "audio/wav"


def test_sarvam_failure_explanation():
    explanation = explain_failure_with_sarvam("oom", "OutOfMemoryError in bitmap allocation", "Budget Android")
    assert "root_cause" in explanation
    assert "developer_fix" in explanation
    assert "code_remedy" in explanation


def test_evaluator_scenarios_api(client):
    res = client.get("/api/v1/evaluator/scenarios")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 2

    # Check Scenario A
    res_a = client.get("/api/v1/evaluator/scenarios/fintech-upi-timeout")
    assert res_a.status_code == 200
    sc_a = res_a.json()
    assert sc_a["category"] == "fintech"
    assert "SocketTimeoutException" in sc_a["logcat"]

    # Check Scenario B
    res_b = client.get("/api/v1/evaluator/scenarios/quick-commerce-oom")
    assert res_b.status_code == 200
    sc_b = res_b.json()
    assert sc_b["category"] == "delivery"
    assert "OutOfMemoryError" in sc_b["logcat"]


def test_sarvam_tts_endpoint(client):
    res = client.post("/api/v1/translate/audio", json={
        "text": "सावधान: यह ऍप 2GB रैम वाले फोन पर क्रैश हो रहा है।",
        "target_language_code": "hi-IN",
        "speaker": "meera",
    })
    assert res.status_code == 200
    data = res.json()
    assert "audio_base64" in data
    assert data["format"] == "audio/wav"


def test_sarvam_explain_endpoint(client):
    res = client.post("/api/v1/explain/failure", json={
        "category": "network",
        "evidence": "java.net.SocketTimeoutException: Connection timed out",
        "persona_id": "edge-village",
    })
    assert res.status_code == 200
    data = res.json()
    assert "root_cause" in data
    assert "developer_fix" in data
    assert "code_remedy" in data


def test_analyze_logs_with_ml_enrichment(client):
    sample_text = (
        "11-21 14:02:10.120 14205 14205 E AndroidRuntime: FATAL EXCEPTION: main\n"
        "Process: com.bharat.app, PID: 14205\n"
        "java.lang.OutOfMemoryError: Failed to allocate a 52428816 byte allocation\n"
        "java.net.SocketTimeoutException: failed to connect to api.bharatsim.io after 15000ms\n"
    )
    res = client.post("/api/v1/analyze/logs", json={
        "text": sample_text,
        "persona_id": "budget-android",
    })
    assert res.status_code == 200
    data = res.json()
    assert "ml_pipeline" in data
    assert data["ml_pipeline"]["algorithm"] == "TF-IDF weighted class-centroid classifier (portable pure Python)"
    assert data["summary"]["finding_count"] >= 2
    # Verify Sarvam explanation is attached to findings
    first_finding = data["findings"][0]
    assert "sarvam_explanation" in first_finding
    assert "code_remedy" in first_finding["sarvam_explanation"]
    assert isinstance(first_finding["ml_classification"], dict)
    assert first_finding["ml_classification"]["category"] == first_finding["kind"]
    assert 0 <= first_finding["ml_classification"]["confidence"] <= 1
    assert first_finding["classification_method"] == "ml_corroborated"



def _comparison_test_db(rows):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE runs (id TEXT PRIMARY KEY, persona_id TEXT, status TEXT, result_json TEXT, owner_id TEXT)"
    )
    connection.executemany(
        "INSERT INTO runs(id,persona_id,status,result_json,owner_id) VALUES(?,?,?,?,?)",
        rows,
    )
    return connection


def _comparison_request(owner_id: str):
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/runs/compare", "headers": []})
    request.state.owner_id = owner_id
    return request


def test_run_comparison_uses_owner_scoped_persisted_telemetry(monkeypatch):
    rows = [
        ("base", "baseline", "completed", json.dumps({
            "telemetry_gfx": {"jank_percentage": 4.0},
            "telemetry_mem": {"total_pss_mb": 90.0},
        }), "owner-a"),
        ("constrained", "budget-android", "completed", json.dumps({
            "telemetry_gfx": {"jank_percentage": 36.0},
            "telemetry_mem": {"total_pss_mb": 290.0},
        }), "owner-a"),
        ("foreign", "baseline", "completed", json.dumps({
            "telemetry_gfx": {"jank_percentage": 1.0},
        }), "owner-b"),
    ]
    connection = _comparison_test_db(rows)

    @contextmanager
    def fake_db():
        yield connection

    monkeypatch.setattr(main_module, "db", fake_db)
    result = main_module.compare_runs(
        CompareRunsRequest(baseline_run_id="base", constrained_run_id="constrained"),
        _comparison_request("owner-a"),
    )

    assert result["baseline_metrics"] == {"jank_percentage": 4.0, "peak_memory_mb": 90.0}
    assert result["constrained_metrics"] == {"jank_percentage": 36.0, "peak_memory_mb": 290.0}
    assert result["anomaly_detected"] is True
    assert 0 <= result["anomaly_score"] <= 100
    memory_anomaly = next(item for item in result["anomalies"] if item["metric"] == "peak_memory_mb")
    assert memory_anomaly["delta_pct"] == 222.2


def test_run_comparison_hides_foreign_owner_run(monkeypatch):
    connection = _comparison_test_db([
        ("base", "baseline", "completed", json.dumps({"telemetry_gfx": {"jank_percentage": 4.0}}), "owner-a"),
        ("foreign", "baseline", "completed", json.dumps({"telemetry_gfx": {"jank_percentage": 1.0}}), "owner-b"),
    ])

    @contextmanager
    def fake_db():
        yield connection

    monkeypatch.setattr(main_module, "db", fake_db)
    with pytest.raises(HTTPException) as exc:
        main_module.compare_runs(
            CompareRunsRequest(baseline_run_id="base", constrained_run_id="foreign"),
            _comparison_request("owner-a"),
        )
    assert exc.value.status_code == 404


def test_run_comparison_rejects_missing_measured_metrics(monkeypatch):
    connection = _comparison_test_db([
        ("base", "baseline", "completed", "{}", "owner-a"),
        ("constrained", "budget-android", "completed", "{}", "owner-a"),
    ])

    @contextmanager
    def fake_db():
        yield connection

    monkeypatch.setattr(main_module, "db", fake_db)
    with pytest.raises(HTTPException) as exc:
        main_module.compare_runs(
            CompareRunsRequest(baseline_run_id="base", constrained_run_id="constrained"),
            _comparison_request("owner-a"),
        )
    assert exc.value.status_code == 422


def test_sarvam_key_supports_legacy_server_variable(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.setenv("sarvam_api", "legacy-server-key-value-123")
    assert main_module.get_sarvam_api_key() == "legacy-server-key-value-123"

    monkeypatch.setenv("SARVAM_API_KEY", "preferred-server-key-value-456")
    assert main_module.get_sarvam_api_key() == "preferred-server-key-value-456"


def test_capabilities_enable_sarvam_when_legacy_server_key_is_configured(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.setenv("sarvam_api", "legacy-server-key-value-123")
    data = main_module.capabilities()
    assert data["sarvam_translation"] is True
    assert data["sarvam_audio_tts"] is True


def test_capabilities_disable_unconfigured_provider_and_database_features(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.delenv("sarvam_api", raising=False)
    monkeypatch.setattr(main_module, "requires_persistent_database", lambda: True)
    monkeypatch.setattr(main_module, "database_is_available", lambda: False)
    monkeypatch.setattr(main_module, "worker_dispatch_configured", lambda: False)
    monkeypatch.setattr(main_module, "STORAGE_ENABLED", False)

    data = main_module.capabilities()
    assert data["sarvam_audio_tts"] is False
    assert data["sarvam_translation"] is False
    assert data["run_comparison"] is False
    assert data["apk_upload"] is False
    assert data["max_upload_mb"] == main_module.MAX_UPLOAD_BYTES // (1024 * 1024)
    assert data["android_execution"] is False


def test_backend_classifier_on_independent_curated_holdout():
    """Small hand-authored holdout; deliberately separate from generated training templates."""
    from app.ml_classifier import classify_log_snippet

    cases = {
        "crash": [
            "E AndroidRuntime: FATAL EXCEPTION: main",
            "Process in.bharatsim.paymock has died: fg TOP",
            "java.lang.NullPointerException: Attempt to invoke virtual method on a null object reference",
            "Fatal signal 11 (SIGSEGV), code 1, fault addr 0x0 in tid 1201",
            "Unable to start activity ComponentInfo{in.example/.CheckoutActivity}",
            "java.lang.IllegalStateException: Fragment not attached to a context",
            "ActivityManager: Force finishing activity in.example/.MainActivity",
            "java.lang.ClassCastException: android.widget.TextView cannot be cast to android.widget.Button",
        ],
        "anr": [
            "ActivityManager: ANR in in.example (in.example/.MainActivity)",
            "Input dispatching timed out: Window is not responding",
            "Application Not Responding: input event dispatch timeout",
            "Reason: Input dispatching timed out while waiting for focused window",
            "ActivityManager: Timeout executing service ServiceRecord",
            "WindowManager: ANR detected for package in.example",
            "Broadcast of Intent android.intent.action.BOOT_COMPLETED timed out",
            "main thread blocked for 5000ms; app not responding",
        ],
        "network": [
            "java.net.SocketTimeoutException: timeout while reading response",
            "java.net.UnknownHostException: Unable to resolve host api.example.in",
            "java.net.ConnectException: Failed to connect to server port 443",
            "javax.net.ssl.SSLHandshakeException: handshake failed",
            "java.net.NoRouteToHostException: No route to host",
            "java.io.IOException: unexpected end of stream on connection",
            "HTTP FAILED: java.net.SocketException: Connection reset",
            "ETIMEDOUT while connecting to payments.example.in",
        ],
        "oom": [
            "java.lang.OutOfMemoryError: Failed to allocate 52428800 bytes",
            "lmkd: Kill 'in.example' to free 51200kB because system is low on memory",
            "Low on memory: reclaiming cached processes",
            "GC_FOR_ALLOC freed 0K, 51200K until OOM",
            "ActivityManager: Killing process due to memory pressure",
            "onTrimMemory level=80, releasing image cache",
            "Failed to allocate a 64MB byte allocation with 8MB free",
            "Process killed by lowmemorykiller oom_adj 900",
        ],
        "storage": [
            "java.io.IOException: write failed: ENOSPC (No space left on device)",
            "android.database.sqlite.SQLiteFullException: database or disk is full",
            "File system full: cannot create cache entry",
            "java.io.IOException: No space left on device while writing /data/user/0",
            "StorageManager: low storage threshold reached",
            "open failed: EIO (I/O error) while writing file",
            "DiskFullException: insufficient free blocks",
            "SQLite database cannot grow because volume is full",
        ],
        "normal": [
            "I ActivityTaskManager: Displayed in.example/.MainActivity for user 0",
            "I Choreographer: Skipped 2 frames! The application may be doing too much work",
            "D ConnectivityService: Network capabilities changed",
            "I ActivityManager: Start proc in.example for activity",
            "D ViewRootImpl: View layout completed in 18ms",
            "I InputMethodManager: showSoftInput() view=EditText",
            "D OkHttp: response received with status 200",
            "I JobScheduler: Job finished successfully",
        ],
    }

    confusion = {label: {pred: 0 for pred in cases} for label in cases}
    total = correct = 0
    for expected, lines in cases.items():
        for line in lines:
            predicted = classify_log_snippet(line)["category"]
            assert predicted in cases
            confusion[expected][predicted] += 1
            total += 1
            correct += predicted == expected

    f1_scores = []
    for label in cases:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[other][label] for other in cases if other != label)
        false_negative = sum(confusion[label][other] for other in cases if other != label)
        precision = true_positive / (true_positive + false_positive or 1)
        recall = true_positive / (true_positive + false_negative or 1)
        f1_scores.append(2 * precision * recall / (precision + recall or 1))

    accuracy = correct / total
    macro_f1 = sum(f1_scores) / len(f1_scores)
    assert total == 48
    assert accuracy >= 0.75, f"curated holdout accuracy regressed: {accuracy:.3f}"
    assert macro_f1 >= 0.75, f"curated holdout macro-F1 regressed: {macro_f1:.3f}"
