from pathlib import Path

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
