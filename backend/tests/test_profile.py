"""Profile endpoints: PATCH /me preferences and POST /change-password."""

from tests.conftest import auth_headers, make_user


def test_patch_me_updates_display_name_and_persists(test_client):
    user, password = make_user(test_client)
    headers = auth_headers(test_client, user["email"], password)
    r = test_client.patch(
        "/api/auth/me", json={"display_name": "Ada Lovelace"}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["display_name"] == "Ada Lovelace"
    me = test_client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["display_name"] == "Ada Lovelace"


def test_patch_me_new_learning_preferences_persist(test_client):
    user, password = make_user(test_client)
    headers = auth_headers(test_client, user["email"], password)
    patch = {
        "preferred_language": "python",
        "experience_level": "intermediate",
        "learning_goal": "projects",
    }
    r = test_client.patch("/api/auth/me", json=patch, headers=headers)
    assert r.status_code == 200, r.text
    for key, value in patch.items():
        assert r.json()[key] == value
    me = test_client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    for key, value in patch.items():
        assert me.json()[key] == value


def test_patch_me_rejects_unknown_language(test_client):
    user, password = make_user(test_client)
    headers = auth_headers(test_client, user["email"], password)
    r = test_client.patch(
        "/api/auth/me",
        json={"preferred_language": "brainfuck"},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_patch_me_rejects_unknown_experience_level(test_client):
    user, password = make_user(test_client)
    headers = auth_headers(test_client, user["email"], password)
    r = test_client.patch(
        "/api/auth/me", json={"experience_level": "wizard"}, headers=headers
    )
    assert r.status_code == 422, r.text


def test_patch_me_rejects_unknown_learning_goal(test_client):
    user, password = make_user(test_client)
    headers = auth_headers(test_client, user["email"], password)
    r = test_client.patch(
        "/api/auth/me", json={"learning_goal": "napping"}, headers=headers
    )
    assert r.status_code == 422, r.text


def test_patch_me_clears_preferences_with_empty_string(test_client):
    user, password = make_user(test_client, name="Clr")
    headers = auth_headers(test_client, user["email"], password)
    test_client.patch(
        "/api/auth/me",
        json={"preferred_language": "go", "experience_level": "beginner"},
        headers=headers,
    )
    r = test_client.patch(
        "/api/auth/me",
        json={"preferred_language": "", "experience_level": ""},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["preferred_language"] == ""
    assert r.json()["experience_level"] == ""


def test_change_password_requires_current_password(test_client):
    user, password = make_user(test_client)
    headers = auth_headers(test_client, user["email"], password)
    r = test_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-password", "new_password": "newsecret456"},
        headers=headers,
    )
    assert r.status_code == 401, r.text


def test_change_password_rejects_same_password(test_client):
    user, password = make_user(test_client)
    headers = auth_headers(test_client, user["email"], password)
    r = test_client.post(
        "/api/auth/change-password",
        json={"current_password": password, "new_password": password},
        headers=headers,
    )
    assert r.status_code == 409, r.text


def test_change_password_rotates_token_and_old_token_dies(test_client):
    user, password = make_user(test_client)
    r = test_client.post(
        "/api/auth/login", json={"email": user["email"], "password": password}
    )
    old_token = r.json()["access_token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    r = test_client.post(
        "/api/auth/change-password",
        json={"current_password": password, "new_password": "brand-new-789"},
        headers=old_headers,
    )
    assert r.status_code == 200, r.text
    new_token = r.json()["access_token"]
    assert new_token != old_token

    # Old token is revoked by the token_version bump...
    assert (
        test_client.get("/api/auth/me", headers=old_headers).status_code == 401
    )
    # ...while the fresh token keeps working, and the new password persists
    # via a completely fresh login.
    new_headers = {"Authorization": f"Bearer {new_token}"}
    assert test_client.get("/api/auth/me", headers=new_headers).status_code == 200
    login = test_client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "brand-new-789"},
    )
    assert login.status_code == 200, login.text
    assert (
        test_client.post(
            "/api/auth/login",
            json={"email": user["email"], "password": password},
        ).status_code
        == 401
    )


def test_change_password_requires_auth(test_client):
    r = test_client.post(
        "/api/auth/change-password",
        json={"current_password": "x", "new_password": "y"},
    )
    assert r.status_code in (401, 403)
