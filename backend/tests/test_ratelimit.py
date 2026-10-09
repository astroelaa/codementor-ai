"""Rate limit tests: exceeding the mentor budget yields 429 + Retry-After."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.deps import get_llm_manager
from app.main import create_app
from tests.conftest import TEST_DB_URL, fake


def test_mentor_rate_limit():
    tight = Settings(database_url=TEST_DB_URL, rate_limit_mentor="2/minute")
    rate_app = create_app(tight)
    rate_app.dependency_overrides[get_llm_manager] = lambda: fake
    rate_client = TestClient(rate_app)

    r = rate_client.post(
        "/api/auth/signup",
        json={"email": "limited@example.com", "password": "secret123"},
    )
    assert r.status_code == 201
    r = rate_client.post(
        "/api/auth/login",
        json={"email": "limited@example.com", "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # 1st mentor call: create the session.
    r = rate_client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]

    # 2nd mentor call: one message.
    r = rate_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "hello"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    # 3rd mentor call within the minute: rejected.
    r = rate_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "again"},
        headers=headers,
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert r.json()["code"] == 429
