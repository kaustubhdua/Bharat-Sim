import io
import os
import zipfile

from fastapi.testclient import TestClient

from app.main import app, validate_apk_archive, validate_runtime_security_config

client = TestClient(app)


def make_zip(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries:
            archive.writestr(name, value)
    return stream.getvalue()


def test_valid_apk_like_archive_passes_manifest_and_bounds(tmp_path):
    path = tmp_path / "valid.apk"
    path.write_bytes(make_zip([("AndroidManifest.xml", b"manifest"), ("classes.dex", b"dex")]))
    validate_apk_archive(path)


def test_arbitrary_zip_without_android_manifest_is_rejected(tmp_path):
    path = tmp_path / "not-apk.apk"
    path.write_bytes(make_zip([("notes.txt", b"not an apk")]))
    try:
        validate_apk_archive(path)
        assert False, "expected invalid APK rejection"
    except Exception as exc:
        assert "AndroidManifest.xml" in str(exc)


def test_api_key_gate_rejects_missing_key(monkeypatch):
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BHARATSIM_API_KEY", "a" * 40)
    response = client.get("/api/v1/personas")
    assert response.status_code == 401


def test_api_key_gate_accepts_correct_key(monkeypatch):
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BHARATSIM_API_KEY", "b" * 40)
    response = client.get("/api/v1/personas", headers={"X-BharatSim-API-Key": "b" * 40})
    assert response.status_code == 200


def test_api_key_gate_fails_closed_without_configured_key(monkeypatch):
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "true")
    monkeypatch.delenv("BHARATSIM_API_KEY", raising=False)
    response = client.get("/api/v1/personas")
    assert response.status_code == 503


def test_production_config_refuses_disabled_api_auth():
    import pytest
    with pytest.raises(RuntimeError, match="BHARATSIM_REQUIRE_API_KEY=true"):
        validate_runtime_security_config({"BHARATSIM_ENV": "production", "BHARATSIM_REQUIRE_API_KEY": "false"})


def test_production_config_refuses_missing_or_weak_api_key():
    import pytest
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        validate_runtime_security_config({"BHARATSIM_ENV": "production", "BHARATSIM_REQUIRE_API_KEY": "true"})
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        validate_runtime_security_config({
            "BHARATSIM_ENV": "production",
            "BHARATSIM_REQUIRE_API_KEY": "true",
            "BHARATSIM_API_KEY": "short",
        })


def test_production_config_accepts_strong_server_side_key():
    validate_runtime_security_config({
        "BHARATSIM_ENV": "production",
        "BHARATSIM_REQUIRE_API_KEY": "true",
        "BHARATSIM_API_KEY": "k" * 40,
    })


def test_development_config_remains_available_without_shared_key():
    validate_runtime_security_config({"BHARATSIM_ENV": "development"})
