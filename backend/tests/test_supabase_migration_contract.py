"""Static contract tests for the additive BharatSim Supabase hardening migration."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase" / "migrations" / "20261027060000_harden_bharatsim_rls_and_indexes.sql"
TABLES = (
    "runs",
    "analyses",
    "workers",
    "run_events",
    "artifacts",
    "quotas",
    "audit_events",
)


def normalized_sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8")).lower()


def test_every_bharatsim_table_has_explicit_deny_policies_for_browser_roles() -> None:
    sql = normalized_sql()
    for table in TABLES:
        policy = rf"create policy deny_client_access_{table} on bharatsim\.{table} for all to anon, authenticated using \(false\) with check \(false\)"
        assert re.search(policy, sql), f"Missing explicit deny policy for bharatsim.{table}"


def test_missing_foreign_key_indexes_are_added() -> None:
    sql = normalized_sql()
    expected = (
        "create index if not exists analyses_run_id_idx on bharatsim.analyses (run_id)",
        "create index if not exists artifacts_owner_id_idx on bharatsim.artifacts (owner_id)",
        "create index if not exists workers_current_run_id_idx on bharatsim.workers (current_run_id)",
    )
    for statement in expected:
        assert statement in sql, f"Missing expected index statement: {statement}"


def test_migration_is_scoped_to_bharatsim_and_does_not_grant_browser_access() -> None:
    sql = normalized_sql()
    assert not re.search(r"\bgenomeguard\s*\.", sql), "Migration must not mutate GenomeGuard objects"
    assert "grant all" not in sql
    assert "to anon, authenticated using (false) with check (false)" in sql
