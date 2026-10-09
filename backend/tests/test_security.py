"""Security tests: no key leakage, token handling, error envelope."""

import jwt

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import TEST_DB_URL, client, make_user

SENTINEL = "gsk-test-sentinel-key-12345"


def test_health_exposes_no_keys():
    r = client.get("/health")
    assert r.status_code == 200
    assert SENTINEL not in r.text
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

    r = bare_client.post(
        "/api/auth/signup",
        json={"email": "bare@example.com", "password": "secret123"},
    )
    assert r.status_code == 201
    r = bare_client.post(
        "/api/auth/login",
        json={"email": "bare@example.com", "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = bare_client.post(
        "/api/sessions", json={"language": "python", "code": "x = 1"}, headers=headers
    )
    session_id = r.json()["id"]
    r = bare_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "help"},
        headers=headers,
    )
    assert r.status_code == 503
    assert SENTINEL not in r.text


def test_expired_token_rejected():
    import time

    payload = {"sub": "nobody", "iat": 1, "exp": int(time.time()) - 10}
    token = jwt.encode(payload, "test-secret-key-do-not-use-in-prod", algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_error_envelope_shape():
    r = client.get("/api/sessions/does-not-exist", headers={})
    assert r.status_code == 404
    body = r.json()
    assert set(body.keys()) == {"detail", "code"}
