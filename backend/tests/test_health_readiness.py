from contextlib import contextmanager

from app import main


class FakeConnection:
    def execute(self, query, parameters=()):
        class Result:
            def fetchall(self):
                return []
            def fetchone(self):
                return {"ok": 1}
        return Result()


def install_database(monkeypatch):
    @contextmanager
    def fake_db():
        yield FakeConnection()
    monkeypatch.setattr(main, "db", fake_db)
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
