from fastapi.testclient import TestClient

from app import main


def test_production_guest_can_run_stateless_log_analysis(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(main, "DATABASE_URL", "")

    client = TestClient(main.app)
    response = client.post(
        "/api/v1/analyze/logs",
        json={
            "persona_id": "budget-android",
            "text": "FATAL EXCEPTION: java.lang.IllegalStateException\n at com.example.app.MainActivity.onCreate(MainActivity.java:42)",
        },
    )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["analysis_mode"] == "deterministic-rule-based"
    assert report["summary"]["critical"] == 1
    assert report["persistence"]["saved"] is False
    assert "not saved" in report["persistence"]["reason"].lower()


def test_production_guest_cannot_analyze_a_private_run(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(main, "DATABASE_URL", "")

    client = TestClient(main.app)
    response = client.post(
        "/api/v1/analyze/logs",
        json={"persona_id": "budget-android", "text": "FATAL EXCEPTION", "run_id": "private-run-id"},
    )

    assert response.status_code == 401, response.text


def test_public_preview_rejects_oversized_log_input(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setattr(main, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(main, "DATABASE_URL", "")

    client = TestClient(main.app)
    response = client.post(
        "/api/v1/analyze/logs",
        json={"persona_id": "budget-android", "text": "x" * (64 * 1024 + 1)},
    )

    assert response.status_code == 413, response.text
