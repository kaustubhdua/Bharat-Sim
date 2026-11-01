import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import main


def prepare(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATABASE_URL", "")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "audit.sqlite3")
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
    main.init_db()


def add_run(run_id, owner_id=None):
    now = main.utcnow()
    with main.db() as conn:
        conn.execute(
            "INSERT INTO runs(id,created_at,status,persona_id,owner_id,updated_at) VALUES(?,?,?,?,?,?)",
            (run_id, now, "queued", "budget-android", owner_id, now),
        )


def test_run_events_and_audit_events_are_written_and_bounded(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    run_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    add_run(run_id, owner_id)

    with main.db() as conn:
        main.record_run_event(conn, run_id, "run_created", "user", owner_id, {"persona_id": "budget-android"})
        main.record_audit_event(conn, owner_id, "user", owner_id, "run.created", "run", run_id, {"size_bytes": 123})
        main.record_audit_event(conn, owner_id, "user", owner_id, "run.metadata", "run", run_id, {"large": "x" * 9000})

    with main.db() as conn:
        event = conn.execute("SELECT * FROM run_events WHERE run_id=?", (run_id,)).fetchone()
        audit = conn.execute("SELECT * FROM audit_events WHERE resource_id=? ORDER BY id", (run_id,)).fetchall()

    assert event["event_type"] == "run_created"
    assert json.loads(event["payload_json"])["persona_id"] == "budget-android"
    assert len(audit) == 2
    assert json.loads(audit[1]["metadata_json"])["truncated"] is True


def test_run_event_endpoint_is_owner_scoped(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    owner_id = str(uuid.uuid4())
    other_owner = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    add_run(run_id, owner_id)
    with main.db() as conn:
        main.record_run_event(conn, run_id, "worker_claimed", "worker", "android-runner-1", {"attempt": 1})

    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    monkeypatch.setattr(main, "verify_supabase_access_token", lambda token: owner_id if token == "owner-token" else other_owner)
    client = TestClient(main.app)

    owner_response = client.get(f"/api/v1/runs/{run_id}/events", headers={"Authorization": "Bearer owner-token"})
    other_response = client.get(f"/api/v1/runs/{run_id}/events", headers={"Authorization": "Bearer other-token"})

    assert owner_response.status_code == 200
    assert owner_response.json()["items"][0]["event_type"] == "worker_claimed"
    assert other_response.status_code == 404


def test_run_events_cascade_when_run_is_deleted_but_audit_remains(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    run_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    add_run(run_id, owner_id)
    with main.db() as conn:
        main.record_run_event(conn, run_id, "run_created", "user", owner_id, {})
        main.record_audit_event(conn, owner_id, "user", owner_id, "run.deleted", "run", run_id, {})
        conn.execute("DELETE FROM runs WHERE id=?", (run_id,))

    with main.db() as conn:
        run_events = conn.execute("SELECT COUNT(*) AS n FROM run_events WHERE run_id=?", (run_id,)).fetchone()["n"]
        audit_events = conn.execute("SELECT COUNT(*) AS n FROM audit_events WHERE resource_id=?", (run_id,)).fetchone()["n"]

    assert run_events == 0
    assert audit_events == 1


def test_event_actor_type_is_validated(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    run_id = str(uuid.uuid4())
    add_run(run_id)
    with pytest.raises(ValueError):
        with main.db() as conn:
            main.record_run_event(conn, run_id, "bad_event", "admin", None, {})
