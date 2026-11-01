import pytest
from fastapi.testclient import TestClient

from app import main


def worker_headers(token):
    return {"X-BharatSim-Worker-Token": token}


def test_production_worker_claim_fails_closed_without_explicit_isolation_approval(monkeypatch):
    token = "w" * 48
    monkeypatch.setattr(main, "APP_ENV", "production")
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


def test_production_worker_claim_requires_all_three_safety_flags(monkeypatch):
    token = "w" * 48
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", token)
    monkeypatch.setenv("BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BHARATSIM_WORKER_ISOLATION_ATTESTED", "true")
    monkeypatch.setenv("BHARATSIM_WORKER_EGRESS_RESTRICTED", "true")
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    monkeypatch.setattr(main, "DB_PATH", main.DB_PATH.parent / "worker-gate-test.sqlite3")
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
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "worker-gate.sqlite3")
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
