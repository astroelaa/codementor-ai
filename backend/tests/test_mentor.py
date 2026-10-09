"""End-to-end mentor flow with the fake LLM: turns, stream, hints, solve."""

import json

from tests.conftest import PYTHON_CODE, client, fake_llm, user_headers  # noqa: F401
from tests.fake_llm import HINT_JSON, JUDGE_FAIL_JSON, JUDGE_PASS_JSON


def _new_session(headers):
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": PYTHON_CODE},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_message_turn_stores_score_and_misconception(user_headers, fake_llm):
    session_id = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "I think len() counts the values."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "empty" in body["reply"]
    assert body["understanding_score"] == 25
    assert body["hints_left"] == 3
    assert body["misconception"]["type"] == "empty-input"
    assert body["provider"] == "fake"

    # Replay shows both messages in order.
    r = client.get(f"/api/sessions/{session_id}", headers=user_headers)
    roles = [m["role"] for m in r.json()["messages"]]
    assert roles == ["user", "assistant"]


def test_streaming_turn_emits_tokens_then_done(user_headers, fake_llm):
    session_id = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{session_id}/messages/stream",
        json={"content": "The last line divides by something."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    events: dict[str, list] = {}
    current = None
    for line in r.text.splitlines():
        if line.startswith("event:"):
            current = line[6:].strip()
        elif line.startswith("data:") and current:
            events.setdefault(current, []).append(json.loads(line[5:]))
    assert events["provider"][0]["provider"] == "fake"
    assert [t["text"] for t in events["token"]] == ["What ", "happens ", "here?"]
    done = events["done"][0]
    assert done["understanding_score"] == 25
    assert done["message_id"]
    assert done["misconception"]["type"] == "empty-input"
    # The stored reply must be the streamed text, not the meta placeholder.
    assert done["reply"] == "What happens here?"
    r = client.get(f"/api/sessions/{session_id}", headers=user_headers)
    stored = [m for m in r.json()["messages"] if m["role"] == "assistant"]
    assert stored and stored[-1]["content"] == "What happens here?"


def test_hint_budget_enforced_server_side(user_headers, fake_llm):
    session_id = _new_session(user_headers)
    for expected_left in (2, 1, 0):
        fake_llm.queue_complete(HINT_JSON)
        r = client.post(f"/api/sessions/{session_id}/hints", headers=user_headers)
        assert r.status_code == 200, r.text
        assert r.json()["hints_left"] == expected_left
    r = client.post(f"/api/sessions/{session_id}/hints", headers=user_headers)
    assert r.status_code == 403


def test_explain_fail_then_pass_solves_session(user_headers, fake_llm):
    session_id = _new_session(user_headers)
    fake_llm.queue_complete(JUDGE_FAIL_JSON)
    r = client.post(
        f"/api/sessions/{session_id}/explain",
        json={"explanation": "It crashes."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["passed"] is False

    r = client.get(f"/api/sessions/{session_id}", headers=user_headers)
    assert r.json()["status"] == "active"

    fake_llm.queue_complete(JUDGE_PASS_JSON)
    r = client.post(
        f"/api/sessions/{session_id}/explain",
        json={
            "explanation": "len([]) is 0, so the division crashes; "
            "checking for empty input first fixes it."
        },
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is True
    assert body["understanding_score"] == 88
    slugs = {b["slug"] for b in body["badges_earned"]}
    assert "first-solve" in slugs
    assert "hint-free-solve" in slugs

    r = client.get(f"/api/sessions/{session_id}", headers=user_headers)
    assert r.json()["status"] == "solved"

    # Solved sessions are read-only.
    r = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "One more question?"},
        headers=user_headers,
    )
    assert r.status_code == 409


def test_misconceptions_and_skills_recorded(user_headers, fake_llm):
    session_id = _new_session(user_headers)
    client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "len() is never zero."},
        headers=user_headers,
    )
    fake_llm.queue_complete(JUDGE_PASS_JSON)
    client.post(
        f"/api/sessions/{session_id}/explain",
        json={"explanation": "Empty list means dividing by zero."},
        headers=user_headers,
    )

    from app.models import Misconception, Skill, SkillProgress

    me = client.get("/api/auth/me", headers=user_headers).json()
    db = client.app.state.session_factory()
    try:
        misc = (
            db.query(Misconception)
            .filter(Misconception.session_id == session_id)
            .all()
        )
        assert len(misc) == 1
        assert misc[0].type == "empty-input"
        skill = db.query(Skill).filter(Skill.slug == "edge-cases").first()
        progress = (
            db.query(SkillProgress)
            .filter(
                SkillProgress.skill_id == skill.id,
                SkillProgress.user_id == me["id"],
            )
            .all()
        )
        assert progress and progress[0].encounters >= 1
        assert progress[0].score >= 10
    finally:
        db.close()
