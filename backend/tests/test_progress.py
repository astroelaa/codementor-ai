"""Progress tests: dashboard data, skills, learning paths. All real rows."""

from tests.conftest import PYTHON_CODE, client, fake_llm  # noqa: F401
from tests.fake_llm import JUDGE_PASS_JSON


def _solve_one_session(headers):
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": PYTHON_CODE},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]
    r = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "len() is never zero."},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return session_id


def test_dashboard_empty_state(user_headers):
    r = client.get("/api/dashboard", headers=user_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_sessions"] == 0
    assert body["solved_sessions"] == 0
    assert body["streak_days"] == 0
    assert body["avg_understanding"] == 0
    assert body["languages"] == []
    assert body["weak_spots"] == []
    assert body["badges"] == []
    assert body["recent_sessions"] == []


def test_dashboard_reflects_real_data(user_headers, fake_llm):
    session_id = _solve_one_session(user_headers)
    fake_llm.queue_complete(JUDGE_PASS_JSON)
    r = client.post(
        f"/api/sessions/{session_id}/explain",
        json={"explanation": "Empty list means dividing by zero."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text

    r = client.get("/api/dashboard", headers=user_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_sessions"] == 1
    assert body["solved_sessions"] == 1
    assert body["streak_days"] >= 1
    assert body["avg_understanding"] == 88
    assert body["languages"] == [{"language": "python", "sessions": 1}]
    assert body["weak_spots"] == [{"type": "empty-input", "count": 1}]
    assert "first-solve" in {b["slug"] for b in body["badges"]}
    assert len(body["recent_sessions"]) == 1
    recent = body["recent_sessions"][0]
    assert recent["id"] == session_id
    assert recent["message_count"] == 4  # user, mentor, explanation, verdict


def test_dashboard_requires_auth():
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/skills").status_code == 401
    assert client.get("/api/learning-path").status_code == 401


def test_skills_endpoint(user_headers, fake_llm):
    _solve_one_session(user_headers)
    r = client.get("/api/skills", headers=user_headers)
    assert r.status_code == 200, r.text
    by_slug = {s["slug"]: s for s in r.json()}
    assert by_slug["edge-cases"]["encounters"] >= 1


def test_learning_path_lifecycle(user_headers, fake_llm):
    r = client.get("/api/learning-path", headers=user_headers)
    assert r.status_code == 200
    assert r.json() is None

    _solve_one_session(user_headers)
    r = client.post("/api/learning-path/regenerate", headers=user_headers)
    assert r.status_code == 200, r.text
    path = r.json()
    assert path["source"] == "weak-spots"
    assert len(path["items"]) >= 1
    assert all(i["status"] == "todo" for i in path["items"])

    r = client.get("/api/learning-path", headers=user_headers)
    assert r.json()["id"] == path["id"]

    item_id = path["items"][0]["id"]
    r = client.patch(
        f"/api/learning-path/items/{item_id}",
        json={"status": "doing"},
        headers=user_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "doing"

    r = client.patch(
        f"/api/learning-path/items/{item_id}",
        json={"status": "finished"},
        headers=user_headers,
    )
    assert r.status_code == 422

    # Regenerating replaces the active path.
    r = client.post("/api/learning-path/regenerate", headers=user_headers)
    assert r.json()["id"] != path["id"]

    # Another user's item is invisible.
    from tests.conftest import auth_headers, make_user

    other, pw = make_user(client)
    other_headers = auth_headers(client, other["email"], pw)
    r = client.patch(
        f"/api/learning-path/items/{item_id}",
        json={"status": "done"},
        headers=other_headers,
    )
    assert r.status_code == 404


def test_learning_path_starter_without_data(user_headers):
    r = client.post("/api/learning-path/regenerate", headers=user_headers)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "starter"
    assert len(r.json()["items"]) == 3
