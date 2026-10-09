"""Auth tests: signup, login, profile, delete account."""

from tests.conftest import auth_headers, client, make_user


def test_signup_login_me():
    user, password = make_user(client)
    assert user["email"].endswith("@example.com")
    assert user["theme"] == "dark"

    headers = auth_headers(client, user["email"], password)
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == user["id"]


def test_signup_duplicate_email():
    user, _ = make_user(client)
    r = client.post(
        "/api/auth/signup",
        json={"email": user["email"], "password": "another-secret-1"},
    )
    assert r.status_code == 409


def test_signup_validation():
    r = client.post(
        "/api/auth/signup",
        json={"email": "not-an-email", "password": "secret123"},
    )
    assert r.status_code == 422
    r = client.post(
        "/api/auth/signup",
        json={"email": "tiny@example.com", "password": "short"},
    )
    assert r.status_code == 422


def test_login_wrong_password():
    user, _ = make_user(client)
    r = client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "wrong-password-1"},
    )
    assert r.status_code == 401


def test_me_requires_auth():
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer junk"})
    assert r.status_code == 401


def test_update_profile_theme():
    user, password = make_user(client)
    headers = auth_headers(client, user["email"], password)
    r = client.patch("/api/auth/me", json={"theme": "light"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["theme"] == "light"
    r = client.patch("/api/auth/me", json={"theme": "neon"}, headers=headers)
    assert r.status_code == 422


def test_delete_account_removes_everything():
    user, password = make_user(client)
    headers = auth_headers(client, user["email"], password)
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1"},
        headers=headers,
    )
    assert r.status_code == 201

    # Wrong password refuses.
    r = client.request(
        "DELETE", "/api/auth/me", json={"password": "nope-nope-nope"}, headers=headers
    )
    assert r.status_code == 401

    r = client.request(
        "DELETE", "/api/auth/me", json={"password": password}, headers=headers
    )
    assert r.status_code == 204

    # The token no longer resolves to a user.
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 401
