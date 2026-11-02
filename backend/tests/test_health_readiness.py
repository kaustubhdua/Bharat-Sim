from contextlib import contextmanager
import asyncio
from io import BytesIO

import pytest

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


def install_database(monkeypatch):
    @contextmanager
    def fake_db():
        yield FakeConnection()
    monkeypatch.setattr(main, "db", fake_db)
    monkeypatch.setattr(main, "DATABASE_URL", "postgresql://user:pass@db.example.com:5432/postgres?sslmode=require")
    monkeypatch.setattr(main, "production_worker_execution_enabled", lambda: False)
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", "")


def test_production_readiness_fails_when_private_storage_is_not_configured(monkeypatch):
    install_database(monkeypatch)
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(main, "STORAGE_ENABLED", False)

    response = main.health_ready()

    assert response.status_code == 503
    assert response.body
    assert b'"database":"available"' in response.body
    assert b'"authentication":"configured"' in response.body
    assert b'"private_storage":"unavailable"' in response.body
    assert b'"status":"not_ready"' in response.body


def test_production_readiness_reports_api_ready_without_claiming_worker_ready(monkeypatch):
    install_database(monkeypatch)
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(main, "STORAGE_ENABLED", True)

    response = main.health_ready()

    assert response.status_code == 200
    assert b'"status":"ready"' in response.body
    assert b'"api_readiness":"ready"' in response.body
    assert b'"execution_readiness":"not_ready"' in response.body
    assert b'"worker_online":false' in response.body


def test_development_readiness_does_not_require_production_auth_or_storage(monkeypatch):
    install_database(monkeypatch)
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    monkeypatch.setattr(main, "SUPABASE_URL", "")
    monkeypatch.setattr(main, "STORAGE_ENABLED", False)

    response = main.health_ready()

    assert response.status_code == 200
    assert b'"status":"ready"' in response.body
    assert b'"authentication_required":false' in response.body
    assert b'"private_storage_required":false' in response.body


def test_production_capabilities_disable_upload_without_persistent_storage(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "STORAGE_ENABLED", False)

    capabilities = main.capabilities()

    assert capabilities["apk_upload"] is False
    assert capabilities["direct_apk_upload"] is False


def test_production_capabilities_require_database_and_storage_for_upload(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "DATABASE_URL", "postgresql://user:pass@db.example.com:5432/postgres?sslmode=require")
    monkeypatch.setattr(main, "STORAGE_ENABLED", True)

    capabilities = main.capabilities()

    assert capabilities["apk_upload"] is True
    assert capabilities["direct_apk_upload"] is True


def test_serverless_database_access_fails_closed_without_postgres(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setenv("VERCEL", "1")

    with pytest.raises(main.HTTPException) as error:
        with main.db():
            pass

    assert error.value.status_code == 503
    assert "Persistent PostgreSQL" in error.value.detail


def test_serverless_readiness_requires_persistent_postgres_and_private_storage(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(main, "STORAGE_ENABLED", False)
    monkeypatch.setenv("VERCEL", "1")

    response = main.health_ready()

    assert response.status_code == 503
    assert b'"database":"unavailable"' in response.body
    assert b'"private_storage_required":true' in response.body
    assert b'"status":"not_ready"' in response.body


def test_serverless_capabilities_hide_database_dependent_actions_without_postgres(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "STORAGE_ENABLED", False)
    monkeypatch.setenv("VERCEL", "1")

    capabilities = main.capabilities()

    assert capabilities["database_persistence"] is False
    assert capabilities["apk_upload"] is False
    assert capabilities["direct_apk_upload"] is False
    assert capabilities["log_analysis"] is True
    assert capabilities["analysis_persistence"] is False
    assert capabilities["failure_fingerprinting"] is True
    assert capabilities["bharat_score"] is True
    assert capabilities["risk_planner"] is True


def test_serverless_runtime_never_initializes_local_sqlite(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setenv("VERCEL", "1")
    assert main.should_initialize_local_database() is False


def test_local_development_can_initialize_sqlite(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert main.should_initialize_local_database() is True


def test_serverless_multipart_apk_upload_requires_private_storage(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setattr(main, "STORAGE_ENABLED", False)
    monkeypatch.setenv("VERCEL", "1")
    upload = main.UploadFile(filename="sample.apk", file=BytesIO(b"PK\\x03\\x04"))

    with pytest.raises(main.HTTPException) as error:
        asyncio.run(main.create_run(None, "budget-android", upload))

    assert error.value.status_code == 503
    assert "Private Supabase Storage" in error.value.detail
