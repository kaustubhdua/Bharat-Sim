from pathlib import Path
import os
import subprocess
import sys

from app import main


def test_default_data_dir_uses_tmp_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert main.default_data_dir() == Path("/tmp/bharatsim")


def test_default_data_dir_uses_project_data_locally(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert main.default_data_dir() == main.APP_DIR.parent / "data"


def test_startup_cleanup_is_disabled_in_serverless_runtime(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setenv("VERCEL", "1")
    assert main.should_run_startup_cleanup() is False


def test_startup_cleanup_is_disabled_in_production(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert main.should_run_startup_cleanup() is False


def test_startup_cleanup_remains_enabled_for_local_development(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert main.should_run_startup_cleanup() is True


def test_vercel_preview_import_and_health_are_safe_without_persistent_secrets(tmp_path):
    env = os.environ.copy()
    env.update({
        "VERCEL": "1",
        "BHARATSIM_ENV": "development",
        "BHARATSIM_DATA_DIR": str(tmp_path),
        "BHARATSIM_AUTH_REQUIRED": "false",
        "BHARATSIM_REQUIRE_API_KEY": "false",
    })
    for key in ("BHARATSIM_DATABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        env.pop(key, None)

    code = """
from fastapi.testclient import TestClient
from app.main import app, DB_PATH
client = TestClient(app)
assert client.get('/health/live').status_code == 200
assert client.get('/health/ready').status_code == 503
assert client.get('/api/v1/personas').status_code == 200
capabilities = client.get('/api/v1/capabilities').json()
assert capabilities['database_persistence'] is False
assert capabilities['apk_upload'] is False
assert capabilities['log_analysis'] is True
assert capabilities['analysis_persistence'] is False
assert capabilities['risk_planner'] is True
assert client.get('/api/v1/runs').status_code == 503
plan = client.post('/api/v1/plan', json={
    'persona_ids': ['budget-android'],
    'app_category': 'general',
    'critical_flows': ['login', 'payment retry'],
    'max_scenarios': 4,
})
assert plan.status_code == 200, plan.text
assert plan.json()['scenarios']
assert not DB_PATH.exists(), 'serverless import must not create ephemeral SQLite'
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_serverless_preview_cannot_dispatch_apks_even_with_worker_flags(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", "w" * 48)
    monkeypatch.setenv("BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BHARATSIM_WORKER_ISOLATION_ATTESTED", "true")
    monkeypatch.setenv("BHARATSIM_WORKER_EGRESS_RESTRICTED", "true")

    assert main.production_worker_execution_enabled() is False
    assert main.capabilities()["worker_dispatch"] is False



def test_vercel_rewrites_browser_deep_links_to_the_fastapi_frontend():
    root = Path(__file__).resolve().parents[2]
    config = __import__("json").loads((root / "vercel.json").read_text(encoding="utf-8"))
    rewrites = config.get("rewrites", [])
    route_pairs = {(route.get("source"), route.get("destination")) for route in rewrites}

    assert ("/runs", "/") in route_pairs
    assert ("/runs/:path*", "/") in route_pairs
    assert ("/analysis", "/") in route_pairs
    assert ("/analyses", "/") in route_pairs
    assert ("/analyses/:path*", "/") in route_pairs

    # API, health and internal worker endpoints must not be rewritten to HTML.
    assert all(
        not source.startswith(("/api", "/health", "/internal"))
        for source, _ in route_pairs
        if isinstance(source, str)
    )


def test_health_readiness_exposes_only_sanitized_database_failure(monkeypatch):
    from contextlib import contextmanager
    from fastapi.testclient import TestClient

    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(main, "STORAGE_API_KEY", "s" * 40)
    monkeypatch.setattr(main, "STORAGE_ENABLED", True)
    monkeypatch.setattr(main, "DATABASE_URL", "postgresql://secret-user:secret-password@private-host/db?sslmode=require")
    monkeypatch.setattr(main, "requires_persistent_database", lambda: True)
    monkeypatch.setattr(main, "validate_database_configuration", lambda *_: None)

    @contextmanager
    def unavailable_database():
        raise OSError("secret-password private-host")
        yield  # pragma: no cover

    monkeypatch.setattr(main, "db", unavailable_database)
    response = TestClient(main.app).get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["database"] == "unavailable"
    assert payload["database_reason"] == "OSError"
    assert payload["private_storage"] == "configured"
    assert "secret-password" not in response.text
    assert "private-host" not in response.text


def test_health_readiness_reports_missing_private_storage_credential(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(main, "APP_ENV", "development")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(main, "STORAGE_API_KEY", "")
    monkeypatch.setattr(main, "STORAGE_ENABLED", False)
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "requires_persistent_database", lambda: False)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "readiness.sqlite3")
    response = TestClient(main.app).get("/health/ready")

    assert response.status_code == 200
    assert response.json()["database_reason"] == "connected"
    assert response.json()["private_storage"] == "unavailable"
    assert response.json()["private_storage_reason"] == "server_storage_credential_missing"
