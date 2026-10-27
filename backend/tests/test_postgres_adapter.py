from app.main import PostgresCompatConnection, postgres_placeholders


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
