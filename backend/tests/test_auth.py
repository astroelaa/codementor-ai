"""Authentication and profile tests backed by Supabase tokens."""

import time
import uuid
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

from tests.conftest import (
    admin_get_user,
    auth_headers,
    client,
    make_guest,
    make_user,
    settings,
)


def _signed_token(*, audience="authenticated", expires_in=3600):
    private_key = ec.generate_private_key(ec.SECP256R1())
    now = int(time.time())
    claims = {
        "sub": str(uuid.uuid4()),
        "aud": audience,
        "role": "authenticated",
        "is_anonymous": False,
        "iat": now,
        "exp": now + expires_in,
        "iss": f"{settings.supabase_url.rstrip('/')}/auth/v1",
    }
    token = jwt.encode(claims, private_key, algorithm="ES256")
    return token, private_key.public_key()


class _FakeJwks:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self.public_key)


def test_me_returns_supabase_identity():
    user, password = make_user(client)
    headers = auth_headers(client, user["email"], password)
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == user["id"]
    assert body["email"] == user["email"]
    assert body["is_anonymous"] is False


def test_guest_identity_is_anonymous():
    guest, headers = make_guest(client)
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == guest["id"]
    assert body["email"] is None
    assert body["is_anonymous"] is True


def test_update_profile_theme():
    user, password = make_user(client)
    headers = auth_headers(client, user["email"], password)
    response = client.patch(
        "/api/auth/me", json={"theme": "light"}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["theme"] == "light"
    response = client.patch(
        "/api/auth/me", json={"theme": "neon"}, headers=headers
    )
    assert response.status_code == 422


def test_delete_account_revokes_supabase_user():
    user, password = make_user(client)
    headers = auth_headers(client, user["email"], password)
    response = client.delete("/api/auth/me", headers=headers)
    assert response.status_code == 204, response.text
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert admin_get_user(user["id"]) is None


def test_requests_without_token_are_rejected():
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_is_rejected(monkeypatch):
    token, public_key = _signed_token(expires_in=-10)
    monkeypatch.setattr(client.app.state, "jwks_client", _FakeJwks(public_key))
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_wrong_audience_is_rejected(monkeypatch):
    token, public_key = _signed_token(audience="anon")
    monkeypatch.setattr(client.app.state, "jwks_client", _FakeJwks(public_key))
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
