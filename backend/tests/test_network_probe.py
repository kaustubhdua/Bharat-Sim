from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ci_network_payload_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BHARATSIM_ENABLE_TEST_NETWORK_PROBE", raising=False)
    monkeypatch.delenv("BHARATSIM_ENV", raising=False)
    response = client.get("/__ci/network-payload")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not found"


def test_ci_network_payload_returns_exact_uncached_bytes_when_opted_in(monkeypatch):
    monkeypatch.setenv("BHARATSIM_ENABLE_TEST_NETWORK_PROBE", "true")
    monkeypatch.setenv("BHARATSIM_ENV", "ci")
    response = client.get("/__ci/network-payload")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-bharatsim-test-payload-bytes"] == "2000000"
    assert len(response.content) == 2_000_000
    assert response.content[:8] == b"B" * 8
