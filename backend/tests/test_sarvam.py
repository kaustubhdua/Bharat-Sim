import io
import json

import pytest
from fastapi.testclient import TestClient

from app import main, sarvam


def test_translation_request_is_rejected_without_provider_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    response = TestClient(main.app).post(
        "/api/v1/translate/report",
        json={"text": "Payment retry failed.", "target_language_code": "hi-IN"},
    )
    assert response.status_code == 503


@pytest.mark.parametrize("language", ["hi-IN", "ta-IN", "mr-IN"])
def test_translation_calls_sarvam_with_server_key_and_supported_language(monkeypatch, language):
    monkeypatch.setenv("SARVAM_API_KEY", "test-server-key-123456789")
    captured = {}

    class FakeResponse(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(json.dumps({"translated_text": "Translated report"}).encode("utf-8"))

    monkeypatch.setattr(sarvam, "urlopen", fake_urlopen)
    response = TestClient(main.app).post(
        "/api/v1/translate/report",
        json={"text": "Payment retry failed.", "target_language_code": language},
    )
    assert response.status_code == 200
    assert response.json()["translated_text"] == "Translated report"
    assert response.json()["provider"] == "sarvam"
    assert captured["url"] == "https://api.sarvam.ai/translate"
    assert captured["payload"]["target_language_code"] == language
    assert captured["payload"]["model"] == "sarvam-translate:v1"
    assert captured["timeout"] == 15
    assert "api-subscription-key" in {key.lower() for key in captured["headers"]}


def test_translation_rejects_oversized_text_and_unknown_language(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-server-key-123456789")
    client = TestClient(main.app)
    too_long = client.post(
        "/api/v1/translate/report",
        json={"text": "x" * 2001, "target_language_code": "hi-IN"},
    )
    unknown = client.post(
        "/api/v1/translate/report",
        json={"text": "Hello", "target_language_code": "fr-FR"},
    )
    assert too_long.status_code == 422
    assert unknown.status_code == 422


def test_translation_provider_rate_limit_is_reported_without_leaking_details(monkeypatch):
    from urllib.error import HTTPError

    monkeypatch.setenv("SARVAM_API_KEY", "test-server-key-123456789")

    def rate_limited(request, timeout):
        raise HTTPError(request.full_url, 429, "rate limit", {}, None)

    monkeypatch.setattr(sarvam, "urlopen", rate_limited)
    response = TestClient(main.app).post(
        "/api/v1/translate/report",
        json={"text": "Payment retry failed.", "target_language_code": "hi-IN"},
    )
    assert response.status_code == 429
    assert "test-server-key" not in response.text


def test_translation_is_auth_protected_when_auth_is_enabled(monkeypatch):
    monkeypatch.setattr(main, "AUTH_REQUIRED", True)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    response = TestClient(main.app).post(
        "/api/v1/translate/report",
        json={"text": "Payment retry failed.", "target_language_code": "hi-IN"},
    )
    assert response.status_code == 401
    monkeypatch.setattr(main, "AUTH_REQUIRED", False)
