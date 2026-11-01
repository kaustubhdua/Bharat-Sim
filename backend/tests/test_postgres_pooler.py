import sys
import types

from app import main


def test_postgres_connection_disables_prepared_statements_for_transaction_pooler(monkeypatch):
    captured = {}

    class FakeConnection:
        def execute(self, query, parameters=()):
            captured.setdefault("executed_sql", []).append(query)
            return self

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    def connect(database_url, **kwargs):
        captured["database_url"] = database_url
        captured.update(kwargs)
        return FakeConnection()

    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.__path__ = []
    fake_psycopg.connect = connect
    fake_rows = types.ModuleType("psycopg.rows")
    fake_rows.dict_row = object()

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setitem(sys.modules, "psycopg.rows", fake_rows)
    monkeypatch.setattr(main, "DATABASE_URL", "postgresql://postgres:not-a-real-password@example.pooler.supabase.com:6543/postgres?sslmode=require")

    with main.db():
        pass

    assert captured["prepare_threshold"] is None
    assert captured["row_factory"] is fake_rows.dict_row
    assert "options" not in captured
    assert captured["executed_sql"] == ["SET LOCAL search_path TO bharatsim, public"]
