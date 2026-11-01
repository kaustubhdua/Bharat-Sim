from datetime import datetime, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app import main


def prepare_quota_database(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "quota.sqlite3")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    main.init_db()


def insert_runs(owner_id, statuses, created_at=None):
    created = created_at or datetime.now(timezone.utc).isoformat()
    with main.db() as conn:
        for index, status in enumerate(statuses):
            conn.execute(
                "INSERT INTO runs(id,created_at,status,persona_id,owner_id,updated_at) VALUES(?,?,?,?,?,?)",
                (f"quota-{owner_id}-{index}", created, status, "budget-android", owner_id, created),
            )


def test_default_quota_limits_two_active_runs_per_user(monkeypatch, tmp_path):
    prepare_quota_database(monkeypatch, tmp_path)
    owner_id = str(uuid.uuid4())
    insert_runs(owner_id, ["queued", "awaiting_worker"])

    with pytest.raises(HTTPException) as error:
        with main.db() as conn:
            main.enforce_run_quota(conn, owner_id)

    assert error.value.status_code == 429
    assert "Active test-run limit reached" in error.value.detail
    assert error.value.headers["Retry-After"] == "60"


def test_daily_quota_counts_completed_and_cancelled_runs(monkeypatch, tmp_path):
    prepare_quota_database(monkeypatch, tmp_path)
    owner_id = str(uuid.uuid4())
    insert_runs(owner_id, ["completed", "cancelled"])
    with main.db() as conn:
        conn.execute(
            "INSERT INTO quotas(owner_id,daily_run_limit,active_run_limit) VALUES(?,?,?)",
            (owner_id, 2, 2),
        )

    with pytest.raises(HTTPException) as error:
        with main.db() as conn:
            main.enforce_run_quota(conn, owner_id)

    assert error.value.status_code == 429
    assert "Daily test-run limit reached" in error.value.detail
    assert int(error.value.headers["Retry-After"]) > 0


def test_run_quotas_are_isolated_between_users(monkeypatch, tmp_path):
    prepare_quota_database(monkeypatch, tmp_path)
    owner_a = str(uuid.uuid4())
    owner_b = str(uuid.uuid4())
    insert_runs(owner_a, ["queued", "running"])

    with main.db() as conn:
        main.enforce_run_quota(conn, owner_b)


def test_quota_is_skipped_for_single_tenant_local_runs(monkeypatch, tmp_path):
    prepare_quota_database(monkeypatch, tmp_path)
    with main.db() as conn:
        main.enforce_run_quota(conn, None)


def test_signed_upload_route_rejects_user_over_active_limit_before_signing(monkeypatch, tmp_path):
    prepare_quota_database(monkeypatch, tmp_path)
    owner_id = str(uuid.uuid4())
    insert_runs(owner_id, ["queued", "awaiting_worker"])
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    monkeypatch.setattr(main, "verify_supabase_access_token", lambda token: owner_id)
    monkeypatch.setattr(main, "STORAGE_ENABLED", True)
    signed_calls = []
    monkeypatch.setattr(main, "create_private_upload_url", lambda path: signed_calls.append(path) or "https://example.supabase.co/storage/v1/object/upload/sign/bucket/" + path + "?token=" + "t" * 48)

    response = TestClient(main.app).post(
        "/api/v1/uploads/sign",
        headers={"Authorization": "Bearer test-user-token"},
        json={
            "persona_id": "budget-android",
            "filename": "build.apk",
            "size_bytes": 123,
            "sha256": "a" * 64,
        },
    )

    assert response.status_code == 429
    assert "Active test-run limit reached" in response.json()["detail"]
    assert signed_calls == []
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
