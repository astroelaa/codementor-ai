"""Email verification + password recovery tests (mocked delivery)."""

from app.services.email import MemoryEmailBackend, get_email_backend
from tests.conftest import auth_headers, client, make_user


def _memory():
    mem = MemoryEmailBackend()
    client.app.dependency_overrides[get_email_backend] = lambda: mem
    return mem


def _teardown_override():
    client.app.dependency_overrides.pop(get_email_backend, None)


def test_verify_flow_success():
    mem = _memory()
    try:
        user, password = make_user(client)
        headers = auth_headers(client, user["email"], password)
        assert user["is_verified"] is False

        r = client.post("/api/auth/resend-verification", headers=headers)
        assert r.status_code == 200, r.text
        assert len(mem.sent) == 2  # signup email + resend
        assert "verify" in mem.sent[1].subject.lower()
        raw = mem.sent[1].text.split("token=")[1].split()[0]

        r = client.post("/api/auth/verify-email", json={"token": raw})
        assert r.status_code == 200, r.text

        # Single use: replay fails.
        r = client.post("/api/auth/verify-email", json={"token": raw})
        assert r.status_code == 400

        r = client.get("/api/auth/me", headers=headers)
        assert r.json()["is_verified"] is True
    finally:
        _teardown_override()


def test_verify_rejects_bad_expired_tokens():
    r = client.post("/api/auth/verify-email", json={"token": "nope-not-real-token"})
    assert r.status_code == 400


def test_resend_rate_limited_per_hour():
    _memory()
    try:
        user, password = make_user(client)
        headers = auth_headers(client, user["email"], password)
        # Signup already issued 1 verify token, so 2 resends fit the
        # 3-per-hour budget and the 3rd is rejected.
        for _ in range(2):
            assert client.post("/api/auth/resend-verification", headers=headers).status_code == 200
        r = client.post("/api/auth/resend-verification", headers=headers)
        assert r.status_code == 429
    finally:
        _teardown_override()


def test_forgot_password_generic_response():
    mem = _memory()
    try:
        user, _ = make_user(client)
        r = client.post("/api/auth/forgot-password", json={"email": user["email"]})
        assert r.status_code == 200
        assert "If an account exists" in r.json()["message"]
        assert len(mem.sent) == 2  # signup verify + reset
        assert "reset" in mem.sent[1].subject.lower()

        # Unknown address: identical response, no email.
        r = client.post(
            "/api/auth/forgot-password", json={"email": "ghost@example.com"}
        )
        assert r.status_code == 200
        assert "If an account exists" in r.json()["message"]
        assert len(mem.sent) == 2
    finally:
        _teardown_override()


def test_reset_password_flow_and_session_revocation():
    mem = _memory()
    try:
        user, password = make_user(client)
        old_headers = auth_headers(client, user["email"], password)
        assert client.get("/api/auth/me", headers=old_headers).status_code == 200

        client.post("/api/auth/forgot-password", json={"email": user["email"]})
        raw = mem.sent[1].text.split("token=")[1].split()[0]

        r = client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": "brand-new-secret-1"},
        )
        assert r.status_code == 200, r.text

        # Reuse fails.
        r = client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": "another-secret-1"},
        )
        assert r.status_code == 400

        # Old session is dead (revoked).
        assert client.get("/api/auth/me", headers=old_headers).status_code == 401

        # New password works.
        new_headers = auth_headers(client, user["email"], "brand-new-secret-1")
        assert client.get("/api/auth/me", headers=new_headers).status_code == 200
    finally:
        _teardown_override()


def test_reset_validation():
    r = client.post(
        "/api/auth/reset-password",
        json={"token": "junk-token-value", "new_password": "short"},
    )
    assert r.status_code == 422  # password too short fails first
    r = client.post(
        "/api/auth/reset-password",
        json={"token": "junk-token-value", "new_password": "long-enough-secret"},
    )
    assert r.status_code == 400
