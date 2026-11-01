from pathlib import Path

from app import main


def test_default_data_dir_uses_tmp_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert main.default_data_dir() == Path("/tmp/bharatsim")


def test_default_data_dir_uses_project_data_locally(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert main.default_data_dir() == main.APP_DIR.parent / "data"
