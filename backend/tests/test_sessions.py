"""Session tests: creation, guest limits, ownership, replay."""

from tests.conftest import PYTHON_CODE, auth_headers, client, make_user, user_headers


def test_create_session_authenticated(user_headers):
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": PYTHON_CODE},
        headers=user_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "active"
    assert body["guest_token"] is None
    assert body["messages"] == []
    assert any(b["slug"] == "first-session" for b in body["badges_earned"])


def test_create_session_validation(user_headers):
    r = client.post(
        "/api/sessions",
        json={"language": "ruby", "code": "x = 1"},
        headers=user_headers,
    )
    assert r.status_code == 422
    r = client.post(
        "/api/sessions", json={"language": "python", "code": ""}, headers=user_headers
    )
    assert r.status_code == 422


def test_guest_gets_one_free_session():
    r = client.post(
        "/api/sessions", json={"language": "python", "code": PYTHON_CODE}
    )
    assert r.status_code == 201, r.text
    guest_token = r.json()["guest_token"]
    assert guest_token

    headers = {"X-Guest-Token": guest_token}
    r = client.post(
        "/api/sessions",
        json={"language": "javascript", "code": "let x = 1;"},
        headers=headers,
    )
    assert r.status_code == 403
    assert "1 free session" in r.json()["detail"]


def test_guest_can_list_and_replay_own_session():
    r = client.post(
        "/api/sessions", json={"language": "python", "code": PYTHON_CODE}
    )
    guest_token = r.json()["guest_token"]
    session_id = r.json()["id"]
    headers = {"X-Guest-Token": guest_token}

    r = client.get("/api/sessions", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get(f"/api/sessions/{session_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["code"] == PYTHON_CODE


def test_session_ownership_is_enforced():
    user_a, pw_a = make_user(client)
    headers_a = auth_headers(client, user_a["email"], pw_a)
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": PYTHON_CODE},
        headers=headers_a,
    )
    session_id = r.json()["id"]

    user_b, pw_b = make_user(client)
    headers_b = auth_headers(client, user_b["email"], pw_b)
    r = client.get(f"/api/sessions/{session_id}", headers=headers_b)
    assert r.status_code == 403

    # Guests cannot see other users' sessions either.
    r = client.get(f"/api/sessions/{session_id}")
    assert r.status_code in (401, 404)


def test_list_requires_identity():
    r = client.get("/api/sessions")
    assert r.status_code == 401
