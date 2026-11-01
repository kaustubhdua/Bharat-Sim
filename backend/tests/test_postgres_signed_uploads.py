import os

import pytest
from fastapi.testclient import TestClient

from app import main


pytestmark = pytest.mark.skipif(
    not os.getenv("BHARATSIM_DATABASE_URL"),
    reason="requires the PostgreSQL integration service",
)


def test_postgres_signed_upload_persists_expected_apk_size(monkeypatch):
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    monkeypatch.setattr(main, "STORAGE_ENABLED", True)
    monkeypatch.setattr(
        main,
        "create_private_upload_url",
        lambda path: "https://example.supabase.co/storage/v1/object/upload/sign/bharatsim-private/"
        + path + "?token=" + "s" * 48,
    )

    response = TestClient(main.app).post(
        "/api/v1/uploads/sign",
        json={
            "persona_id": "budget-android",
            "filename": "build.apk",
            "size_bytes": 12345,
            "sha256": "a" * 64,
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert response.json()["tus_endpoint"] == "https://example.storage.supabase.co/storage/v1/upload/resumable"

    try:
        with main.db() as conn:
            row = conn.execute(
                "SELECT apk_size_bytes,status FROM runs WHERE id=?",
                (run_id,),
            ).fetchone()
        assert row["apk_size_bytes"] == 12345
        assert row["status"] == "awaiting_worker"
    finally:
        with main.db() as conn:
            conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
