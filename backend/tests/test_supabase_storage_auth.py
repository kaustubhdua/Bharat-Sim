from app import main


def test_modern_supabase_secret_key_is_sent_only_as_apikey(monkeypatch):
    secret = "sb_secret_" + "s" * 48
    monkeypatch.setattr(main, "SUPABASE_SECRET_KEY", secret)
    monkeypatch.setattr(main, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(main, "STORAGE_API_KEY", secret)

    headers = main._storage_headers("application/json")

    assert headers["apikey"] == secret
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers


def test_legacy_supabase_service_role_jwt_remains_supported(monkeypatch):
    legacy = "eyJhbGciOiJIUzI1NiJ9." + "a" * 48
    monkeypatch.setattr(main, "SUPABASE_SECRET_KEY", "")
    monkeypatch.setattr(main, "SUPABASE_SERVICE_ROLE_KEY", legacy)
    monkeypatch.setattr(main, "STORAGE_API_KEY", legacy)

    headers = main._storage_headers()

    assert headers["apikey"] == legacy
    assert headers["Authorization"] == "Bearer " + legacy
