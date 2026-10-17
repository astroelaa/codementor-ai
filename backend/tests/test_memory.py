"""Memory: recap builder, project injection, inspect/delete endpoints."""

from app.services.memory import build_project_context, build_session_recap
from tests.conftest import PYTHON_CODE, auth_headers, client, make_user


def _session_with_misc(headers):
    r = client.post(
        "/api/sessions", json={"language": "python", "code": PYTHON_CODE}, headers=headers
    )
    sid = r.json()["id"]
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "len() is never zero."},
        headers=headers,
    )
    return sid


def test_recap_builder_content():
    from app.models import Message, Session as DebugSession

    s = DebugSession(language="python", goal="debug", code="x", understanding_score=40, hints_used=1)
    assert "python" in build_session_recap(s, 0)
    assert "40" in build_session_recap(s, 0)

    m = Message(session_id="s", role="assistant", content="What happens on empty input?")
    s.messages.append(m)
    recap = build_session_recap(s, 2)
    assert "What happens on empty input?" in recap


def test_project_context_empty_and_filled(user_headers):
    from app.models import Session as DebugSession

    db = client.app.state.session_factory()
    try:
        s = DebugSession(language="python", goal="debug", code="x")
        assert build_project_context(db, s) == ""

        r = client.post(
            "/api/projects",
            json={"title": "P", "language": "python"},
            headers=user_headers,
        )
        pid = r.json()["id"]
        r = client.post(
            f"/api/projects/{pid}/milestones", json={"title": "M1"}, headers=user_headers
        )
        mid = r.json()["id"]
        client.post(
            f"/api/projects/milestones/{mid}/tasks",
            json={"title": "T1"},
            headers=user_headers,
        )
        s.project_id = pid
        me = client.get("/api/auth/me", headers=user_headers).json()
        s.user_id = me["id"]
        ctx = build_project_context(db, s)
        assert "P" in ctx
        assert "T1" in ctx
    finally:
        db.close()


def test_prompt_includes_recap_and_project():
    from app.mentor_prompts import chat_system_prompt as chat

    prompt = chat(
        language="python",
        code="x = 1",
        hints_left=3,
        recap="Session recap (python, score 10).",
        project_context="Project 'P'. Current task: 'T1'.",
    )
    assert "Session recap" in prompt
    assert "Current task" in prompt


def test_memory_read_and_delete(user_headers, fake_llm):
    _session_with_misc(user_headers)
    r = client.get("/api/memory", headers=user_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["weak_spots"] == [{"type": "empty-input", "count": 1}]
    assert len(body["misconceptions"]) == 1
    mid = body["misconceptions"][0]["id"]

    other, pw = make_user(client)
    other_headers = auth_headers(client, other["email"], pw)
    assert client.delete(f"/api/memory/misconceptions/{mid}", headers=other_headers).status_code == 404

    r = client.delete(f"/api/memory/misconceptions/{mid}", headers=user_headers)
    assert r.status_code == 200
    assert client.get("/api/memory", headers=user_headers).json()["misconceptions"] == []


def test_memory_requires_auth():
    assert client.get("/api/memory").status_code == 401
