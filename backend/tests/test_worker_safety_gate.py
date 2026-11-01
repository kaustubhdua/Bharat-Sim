from contextlib import contextmanager

from fastapi.testclient import TestClient

from app import main


class FakeConnection:
    def execute(self, query, parameters=()):
        class Result:
            def fetchall(self):
                return []
            def fetchone(self):
                if "to_regclass" in query:
                    return {"runs": "bharatsim.runs", "run_events": "bharatsim.run_events", "audit_events": "bharatsim.audit_events"}
                return {"ok": 1}
        return Result()


@contextmanager
def fake_postgres():
    yield FakeConnection()


def worker_headers(token):
    return {"X-BharatSim-Worker-Token": token}


def test_production_worker_claim_fails_closed_without_explicit_isolation_approval(monkeypatch):
    token = "w" * 48
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", token)
    monkeypatch.setenv("BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BHARATSIM_WORKER_ISOLATION_ATTESTED", "true")
    monkeypatch.delenv("BHARATSIM_WORKER_EGRESS_RESTRICTED", raising=False)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")

    response = TestClient(main.app).post(
        "/internal/worker/claim",
        headers=worker_headers(token),
        json={"worker_id": "android-worker-01"},
    )

    assert response.status_code == 503
    assert "Public APK execution is disabled" in response.json()["detail"]


def test_production_worker_claim_requires_all_three_safety_flags(monkeypatch, tmp_path):
    token = "w" * 48
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "worker-gate-test.sqlite3")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", token)
    monkeypatch.setenv("BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BHARATSIM_WORKER_ISOLATION_ATTESTED", "true")
    monkeypatch.setenv("BHARATSIM_WORKER_EGRESS_RESTRICTED", "true")
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    main.init_db()

    response = TestClient(main.app).post(
        "/internal/worker/claim",
        headers=worker_headers(token),
        json={"worker_id": "android-worker-01"},
    )

    assert response.status_code == 200
    assert response.json() == {"job": None}


def test_development_worker_claim_does_not_require_production_attestation(monkeypatch, tmp_path):
    token = "w" * 48
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "worker-gate.sqlite3")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", token)
    monkeypatch.delenv("BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("BHARATSIM_WORKER_ISOLATION_ATTESTED", raising=False)
    monkeypatch.delenv("BHARATSIM_WORKER_EGRESS_RESTRICTED", raising=False)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    main.init_db()

    response = TestClient(main.app).post(
        "/internal/worker/claim",
        headers=worker_headers(token),
        json={"worker_id": "local-emulator"},
    )

    assert response.status_code == 200
    assert response.json() == {"job": None}


def test_capabilities_hide_production_worker_dispatch_until_gate_is_open(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", "w" * 48)
    monkeypatch.setenv("BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("BHARATSIM_WORKER_ISOLATION_ATTESTED", "true")
    monkeypatch.setenv("BHARATSIM_WORKER_EGRESS_RESTRICTED", "true")
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")

    response = TestClient(main.app).get("/api/v1/capabilities")

    assert response.status_code == 200
    assert response.json()["worker_dispatch"] is False


def test_readiness_names_closed_worker_safety_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "DATABASE_URL", "postgresql://user:pass@db.example.com:5432/postgres?sslmode=require")
    monkeypatch.setattr(main, "db", fake_postgres)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "readiness.sqlite3")
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(main, "STORAGE_ENABLED", True)
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", "w" * 48)
    monkeypatch.setenv("BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("BHARATSIM_WORKER_ISOLATION_ATTESTED", "false")
    monkeypatch.setenv("BHARATSIM_WORKER_EGRESS_RESTRICTED", "false")
    main.init_db()

    response = TestClient(main.app).get("/health/ready")

    assert response.status_code == 200
    assert response.json()["apk_execution_worker"] == "safety_gate_closed"
    assert response.json()["worker_execution_enabled"] is False
    assert response.json()["execution_readiness"] == "not_ready"
