import os
import uuid

import pytest
from fastapi import HTTPException

from app import main


pytestmark = pytest.mark.skipif(
    not os.getenv("BHARATSIM_DATABASE_URL"),
    reason="requires the PostgreSQL integration service",
)


def test_postgres_quota_uses_transaction_locked_owner_row():
    owner_id = str(uuid.uuid4())
    created = main.utcnow()

    with main.db() as conn:
        conn.execute("INSERT INTO auth.users(id) VALUES(?)", (owner_id,))
        conn.execute(
            "INSERT INTO quotas(owner_id,daily_run_limit,active_run_limit) VALUES(?,?,?)",
            (owner_id, 10, 1),
        )
        conn.execute(
            "INSERT INTO runs(id,owner_id,created_at,updated_at,status,persona_id) VALUES(?,?,?,?,?,?)",
            ("quota-postgres-" + owner_id, owner_id, created, created, "queued", "budget-android"),
        )

    with pytest.raises(HTTPException) as error:
        with main.db() as conn:
            main.enforce_run_quota(conn, owner_id)

    assert error.value.status_code == 429
    assert "Active test-run limit reached" in error.value.detail
