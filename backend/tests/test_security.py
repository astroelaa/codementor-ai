"""Security tests: no key leakage, error envelope."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import (
    TEST_DB_URL,
    auth_headers,
    client,
    make_user,
    settings,
)

SENTINEL = "gsk-test-sentinel-key-12345"


def test_health_exposes_no_keys():
    r = client.get("/health")
    assert r.status_code == 200
    assert SENTINEL not in r.text
    assert settings.supabase_service_role_key not in r.text
    assert "api_key" not in r.text.lower()
    assert r.json()["providers_configured"] == ["groq"]


def test_unconfigured_providers_return_503_without_leak():
    bare = Settings(
        database_url=TEST_DB_URL,
        groq_api_key="",
        gemini_api_key="",
        openai_api_key="",
        anthropic_api_key="",
        llm_api_key="",
    )
    bare_app = create_app(bare)
    bare_client = TestClient(bare_app)

    user, password = make_user(bare_client)
    headers = auth_headers(bare_client, user["email"], password)
    r = bare_client.post(
        "/api/sessions", json={"language": "python", "code": "x = 1"}, headers=headers
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]
    r = bare_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "help"},
        headers=headers,
    )
    assert r.status_code == 503
    assert SENTINEL not in r.text


def test_error_envelope_shape(user_headers):
    r = client.get("/api/sessions/does-not-exist", headers=user_headers)
    assert r.status_code == 404
    body = r.json()
    assert set(body.keys()) == {"detail", "code"}
