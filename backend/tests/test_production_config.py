from app.main import validate_runtime_security_config


def production_environment():
    return {
        "BHARATSIM_ENV": "production",
        "BHARATSIM_AUTH_REQUIRED": "true",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "server-only-test-credential-" + "x" * 24,
        "BHARATSIM_STORAGE_BUCKET": "bharatsim-private",
    }


def test_production_accepts_supabase_auth_without_browser_shared_key():
    values = production_environment()
    values["BHARATSIM_REQUIRE_API_KEY"] = "false"
    validate_runtime_security_config(values)


def test_production_rejects_missing_supabase_auth():
    values = production_environment()
    values["BHARATSIM_AUTH_REQUIRED"] = "false"
    try:
        validate_runtime_security_config(values)
    except RuntimeError as exc:
        assert "BHARATSIM_AUTH_REQUIRED" in str(exc)
    else:
        raise AssertionError("production startup must reject disabled user authentication")


def test_production_rejects_missing_server_side_storage_credential():
    values = production_environment()
    values["SUPABASE_SERVICE_ROLE_KEY"] = ""
    try:
        validate_runtime_security_config(values)
    except RuntimeError as exc:
        assert "SUPABASE_SERVICE_ROLE_KEY" in str(exc)
    else:
        raise AssertionError("production startup must reject missing server-only storage credentials")



def test_production_accepts_modern_supabase_secret_key_without_legacy_jwt():
    values = production_environment()
    values["SUPABASE_SERVICE_ROLE_KEY"] = ""
    values["SUPABASE_SECRET_KEY"] = "sb_secret_" + "x" * 48
    validate_runtime_security_config(values)
