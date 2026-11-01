from fastapi.testclient import TestClient

from app import main


def configure_upload_test(monkeypatch, tmp_path, actual_size=123):
    data_dir = tmp_path / "signed-upload-data"
    data_dir.mkdir()
    monkeypatch.setattr(main, "DB_PATH", data_dir / "bharatsim.sqlite3")
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "UPLOAD_DIR", data_dir / "uploads")
    main.UPLOAD_DIR.mkdir()
    main.init_db()
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    monkeypatch.setattr(main, "STORAGE_ENABLED", True)
    monkeypatch.setattr(main, "create_private_upload_url", lambda path: "https://example.supabase.co/storage/v1/object/upload/sign/bucket/" + path + "?token=temporary")
    monkeypatch.setattr(main, "private_object_size", lambda path: actual_size)
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", "worker-test-token-" + "x" * 32)
    return TestClient(main.app)


def test_signed_upload_is_only_queued_after_storage_verification(monkeypatch, tmp_path):
    client = configure_upload_test(monkeypatch, tmp_path)
    ticket = client.post(
        "/api/v1/uploads/sign",
        json={
            "persona_id": "budget-android",
            "filename": "build.apk",
            "size_bytes": 123,
            "sha256": "a" * 64,
        },
    )
    assert ticket.status_code == 200
    payload = ticket.json()
    assert payload["run_id"]
    assert payload["signed_url"].startswith("https://example.supabase.co/")
    assert "SUPABASE_SERVICE_ROLE_KEY" not in payload["signed_url"]
    assert payload["expires_in_seconds"] == 7200

    with main.db() as conn:
        row = conn.execute("SELECT status,apk_size_bytes,apk_storage_path FROM runs WHERE id=?", (payload["run_id"],)).fetchone()
    assert row["status"] == "awaiting_worker"
    assert row["apk_size_bytes"] == 123
    assert row["apk_storage_path"].startswith("runs/")

    completed = client.post(f"/api/v1/runs/{payload['run_id']}/upload-complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "queued"
    assert completed.json()["apk"]["size_bytes"] == 123


def test_signed_upload_rejects_missing_storage_and_bad_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "STORAGE_ENABLED", False)
    client = TestClient(main.app)
    disabled = client.post(
        "/api/v1/uploads/sign",
        json={"persona_id": "budget-android", "filename": "build.apk", "size_bytes": 123, "sha256": "a" * 64},
    )
    assert disabled.status_code == 503

    monkeypatch.setattr(main, "STORAGE_ENABLED", True)
    bad = client.post(
        "/api/v1/uploads/sign",
        json={"persona_id": "budget-android", "filename": "notes.txt", "size_bytes": 123, "sha256": "a" * 64},
    )
    assert bad.status_code == 415


def test_signed_upload_confirmation_rejects_missing_or_mismatched_object(monkeypatch, tmp_path):
    client = configure_upload_test(monkeypatch, tmp_path, actual_size=None)
    ticket = client.post(
        "/api/v1/uploads/sign",
        json={"persona_id": "budget-android", "filename": "build.apk", "size_bytes": 123, "sha256": "b" * 64},
    ).json()
    missing = client.post(f"/api/v1/runs/{ticket['run_id']}/upload-complete")
    assert missing.status_code == 409

    deleted = []
    monkeypatch.setattr(main, "private_object_size", lambda path: 124)
    monkeypatch.setattr(main, "delete_private_object", lambda path: deleted.append(path))
    mismatch = client.post(f"/api/v1/runs/{ticket['run_id']}/upload-complete")
    assert mismatch.status_code == 422
    assert deleted


def test_signed_upload_routes_require_supabase_auth_when_enabled(monkeypatch):
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    response = TestClient(main.app).post(
        "/api/v1/uploads/sign",
        json={"persona_id": "budget-android", "filename": "build.apk", "size_bytes": 123, "sha256": "c" * 64},
    )
    assert response.status_code == 401
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
