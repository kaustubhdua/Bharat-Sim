import io
import zipfile

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_and_capabilities_are_honest():
    assert client.get("/health/live").json()["status"] == "alive"
    ready = client.get("/health/ready").json()
    assert ready["execution_capability"] == "external-worker-required"
    caps = client.get("/api/v1/capabilities").json()
    assert caps["log_analysis"] is True
    # Partial Android Emulator controls are real, but full persona shaping is not.
    assert caps["network_shaping"] is False
    network = caps["emulator_network_controls"]
    assert network["latency"] is True
    assert network["bandwidth"] is True
    assert network["configuration_readback"] is True
    assert network["packet_loss"] is False
    assert network["outage_and_recovery"] is False
    assert network["arbitrary_app_traffic_verified"] is False


def test_personas_and_plan():
    personas = client.get("/api/v1/personas").json()["items"]
    assert len(personas) >= 4
    response = client.post("/api/v1/plan", json={
        "persona_ids": ["baseline", "edge-village"],
        "critical_flows": ["cold start", "payment retry"],
        "max_scenarios": 3,
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["scenarios"]) == 3
    assert data["scenarios"][0]["risk_score"] >= data["scenarios"][-1]["risk_score"]


def test_log_analysis_persists_report():
    response = client.post("/api/v1/analyze/logs", json={
        "text": "FATAL EXCEPTION: main\njava.net.SocketTimeoutException: timeout",
        "persona_id": "budget-android",
    })
    assert response.status_code == 200
    assert response.json()["summary"]["finding_count"] == 2
    assert client.get("/api/v1/analyses").status_code == 200


def test_unknown_persona_rejected():
    response = client.post("/api/v1/analyze/logs", json={"text": "hello", "persona_id": "missing"})
    assert response.status_code == 422


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch, tmp_path):
    from app import main

    monkeypatch.setattr(main, "DB_PATH", tmp_path / "missing" / "unavailable.sqlite3")
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_run_registration_requires_an_apk():
    response = client.post("/api/v1/runs", data={"persona_id": "baseline"})
    assert response.status_code == 422
    assert any(item.get("loc", [])[-1:] == ["apk"] for item in response.json()["detail"])


def test_readiness_does_not_confuse_worker_configuration_with_liveness(monkeypatch, tmp_path):
    from app import main

    data_dir = tmp_path / "readiness-data"
    data_dir.mkdir()
    monkeypatch.setattr(main, "DB_PATH", data_dir / "readiness.sqlite3")
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "UPLOAD_DIR", data_dir / "uploads")
    main.UPLOAD_DIR.mkdir()
    main.init_db()
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", "worker-readiness-secret-" + "x" * 32)

    offline = client.get("/health/ready")
    assert offline.status_code == 200
    assert offline.json()["api_readiness"] == "ready"
    assert offline.json()["execution_readiness"] == "not_ready"
    assert offline.json()["apk_execution_worker"] == "offline"
    assert offline.json()["worker_online"] is False

    with main.db() as conn:
        conn.execute(
            "INSERT INTO workers(id,last_seen,status,current_run_id) VALUES(?,?,?,NULL)",
            ("readiness-test-worker", main.utcnow(), "idle"),
        )
    online = client.get("/health/ready")
    assert online.status_code == 200
    assert online.json()["execution_readiness"] == "ready"
    assert online.json()["apk_execution_worker"] == "online"
    assert online.json()["worker_online"] is True


def test_readiness_reports_worker_not_configured(monkeypatch):
    monkeypatch.delenv("BHARATSIM_WORKER_TOKEN", raising=False)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["api_readiness"] == "ready"
    assert response.json()["execution_readiness"] == "not_ready"
    assert response.json()["apk_execution_worker"] == "not_configured"


def test_supabase_auth_required_and_run_data_is_owner_scoped(monkeypatch, tmp_path):
    from app import main

    data_dir = tmp_path / "auth-data"
    data_dir.mkdir()
    monkeypatch.setattr(main, "DB_PATH", data_dir / "auth.sqlite3")
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "UPLOAD_DIR", data_dir / "uploads")
    main.UPLOAD_DIR.mkdir()
    main.init_db()
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    monkeypatch.setattr(
        main, "verify_supabase_access_token",
        lambda token: {
            "user-a-token": "11111111-1111-4111-8111-111111111111",
            "user-b-token": "22222222-2222-4222-8222-222222222222",
        }[token],
    )

    assert client.get("/api/v1/runs").status_code == 401
    user_a = {"Authorization": "Bearer user-a-token"}
    user_b = {"Authorization": "Bearer user-b-token"}

    apk = io.BytesIO()
    with zipfile.ZipFile(apk, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", b"fixture")
        archive.writestr("classes.dex", b"fixture")
    created = client.post(
        "/api/v1/runs",
        headers=user_a,
        data={"persona_id": "baseline"},
        files={"apk": ("owner-test.apk", apk.getvalue(), "application/vnd.android.package-archive")},
    )
    assert created.status_code == 200
    run_id = created.json()["id"]

    assert [item["id"] for item in client.get("/api/v1/runs", headers=user_a).json()["items"]] == [run_id]
    assert client.get("/api/v1/runs", headers=user_b).json()["items"] == []
    assert client.get(f"/api/v1/runs/{run_id}", headers=user_a).status_code == 200
    assert client.get(f"/api/v1/runs/{run_id}", headers=user_b).status_code == 404

    analysis_a = client.post(
        "/api/v1/analyze/logs", headers=user_a,
        json={"text": "FATAL EXCEPTION: main", "persona_id": "baseline"},
    )
    assert analysis_a.status_code == 200
    assert len(client.get("/api/v1/analyses", headers=user_a).json()["items"]) == 1
    assert client.get("/api/v1/analyses", headers=user_b).json()["items"] == []


def test_supabase_auth_rejects_invalid_access_tokens(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "verify_supabase_access_token", lambda token: (_ for _ in ()).throw(ValueError("bad token")))
    response = client.get("/api/v1/runs", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
