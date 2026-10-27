from app.main import (
    PostgresCompatConnection,
    postgres_placeholders,
    validate_database_configuration,
)

import pytest


class FakeConnection:
    def __init__(self):
        self.calls = []

    def execute(self, query, parameters=()):
        self.calls.append((query, parameters))
        return "cursor"

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_postgres_placeholder_translation_preserves_quoted_question_marks():
    sql = "SELECT * FROM runs WHERE id=? AND note='is this ok?' AND label=\"why?\" AND status=?"
    assert postgres_placeholders(sql) == (
        "SELECT * FROM runs WHERE id=%s AND note='is this ok?' AND label=\"why?\" AND status=%s"
    )


def test_postgres_connection_adapter_forwards_parameters_without_interpolation():
    raw = FakeConnection()
    conn = PostgresCompatConnection(raw)
    assert conn.execute("SELECT * FROM runs WHERE id=?", ("run-1",)) == "cursor"
    assert raw.calls == [("SELECT * FROM runs WHERE id=%s", ("run-1",))]



def test_remote_postgres_requires_explicit_tls():
    validate_database_configuration(
        "postgresql://app:secret@db.example.supabase.co:5432/postgres?sslmode=require",
        "production",
    )
    validate_database_configuration(
        "postgresql://app:secret@db.example.supabase.co:5432/postgres?sslmode=verify-full",
        "production",
    )


@pytest.mark.parametrize(
    "url,environment",
    [
        ("postgresql://app:secret@db.example.supabase.co:5432/postgres", "production"),
        ("postgresql://app:secret@db.example.supabase.co:5432/postgres?sslmode=prefer", "production"),
        ("postgresql://app:secret@db.example.supabase.co:5432/postgres?sslmode=disable", "development"),
        ("", "production"),
        ("not-a-postgres-url", "development"),
    ],
)
def test_unsafe_or_missing_database_configuration_fails_closed(url, environment):
    with pytest.raises(RuntimeError):
        validate_database_configuration(url, environment)


def test_local_development_postgres_can_disable_tls_explicitly():
    validate_database_configuration(
        "postgresql://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable",
        "development",
    )
