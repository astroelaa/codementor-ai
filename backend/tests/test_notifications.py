"""Notifications: persistence, ownership, retention, preferences."""

from app.services.email import MemoryEmailBackend, get_email_backend
from tests.conftest import PYTHON_CODE, auth_headers, client, fake_llm, make_user  # noqa: F401
from tests.fake_llm import JUDGE_PASS_JSON


def _mem():
    mem = MemoryEmailBackend()
    client.app.dependency_overrides[get_email_backend] = lambda: mem
    return mem


def _teardown():
    client.app.dependency_overrides.pop(get_email_backend, None)


def _authed():
    user, pw = make_user(client)
    return auth_headers(client, user["email"], pw)


def test_welcome_notification_on_signup():
    headers = _authed()
    r = client.get("/api/notifications", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    assert items[0]["type"] == "welcome"
    assert items[0]["read"] is False

    r = client.get("/api/notifications/unread-count", headers=headers)
    assert r.json() == {"count": 1}


def test_mark_read_and_read_all(user_headers):
    client.get("/api/notifications", headers=user_headers)
    items = client.get("/api/notifications", headers=user_headers).json()
    nid = items[0]["id"]

    r = client.patch(f"/api/notifications/{nid}/read", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["read"] is True
    assert client.get("/api/notifications/unread-count", headers=user_headers).json() == {"count": 0}

    r = client.post("/api/notifications/read-all", headers=user_headers)
    assert r.status_code == 200


def test_notifications_isolated_per_user(user_headers):
    items = client.get("/api/notifications", headers=user_headers).json()
    nid = items[0]["id"]
    other, pw = make_user(client)
    other_headers = auth_headers(client, other["email"], pw)

    assert client.patch(f"/api/notifications/{nid}/read", headers=other_headers).status_code == 404
    # The other user only sees their own welcome notification.
    assert len(client.get("/api/notifications", headers=other_headers).json()) == 1


def test_solve_and_badge_emit_notifications(user_headers, fake_llm):
    r = client.post(
        "/api/sessions", json={"language": "python", "code": PYTHON_CODE}, headers=user_headers
    )
    sid = r.json()["id"]
    client.post(f"/api/sessions/{sid}/messages", json={"content": "len is never zero."}, headers=user_headers)
    fake_llm.queue_complete(JUDGE_PASS_JSON)
    client.post(
        f"/api/sessions/{sid}/explain",
        json={"explanation": "Empty list means dividing by zero, so guard it first."},
        headers=user_headers,
    )
    types = {n["type"] for n in client.get("/api/notifications", headers=user_headers).json()}
    assert "solve" in types
    assert "badge" in types


def test_progress_email_only_when_opted_in(user_headers, fake_llm):
    mem = _mem()
    try:
        # Default prefs: no progress email.
        r = client.post(
            "/api/sessions", json={"language": "python", "code": PYTHON_CODE}, headers=user_headers
        )
        sid = r.json()["id"]
        client.post(f"/api/sessions/{sid}/messages", json={"content": "x"}, headers=user_headers)
        fake_llm.queue_complete(JUDGE_PASS_JSON)
        client.post(f"/api/sessions/{sid}/explain", json={"explanation": "y" * 20}, headers=user_headers)
        assert mem.sent == []

        # Opt in: next solve sends exactly one.
        r = client.patch("/api/auth/me", json={"notify_progress_emails": True}, headers=user_headers)
        assert r.json()["notify_progress_emails"] is True
        r = client.post(
            "/api/sessions", json={"language": "python", "code": PYTHON_CODE}, headers=user_headers
        )
        sid2 = r.json()["id"]
        client.post(f"/api/sessions/{sid2}/messages", json={"content": "x"}, headers=user_headers)
        fake_llm.queue_complete(JUDGE_PASS_JSON)
        client.post(f"/api/sessions/{sid2}/explain", json={"explanation": "y" * 20}, headers=user_headers)
        assert len(mem.sent) == 1
        assert "solved" in mem.sent[0].subject.lower()
    finally:
        _teardown()


def test_retention_caps_at_100(user_headers):
    from app.models import Notification

    db = client.app.state.session_factory()
    try:
        me = client.get("/api/auth/me", headers=user_headers).json()
        for i in range(105):
            db.add(Notification(user_id=me["id"], type="test", title=f"t{i}"))
        db.commit()
        from app.services.notifications import notify

        notify(db, me["id"], "test", "one-more")
        db.commit()
        remaining = (
            db.query(Notification).filter(Notification.user_id == me["id"]).count()
        )
        assert remaining == 100
    finally:
        db.close()


def test_delete_account_removes_notifications(user_headers):
    items = client.get("/api/notifications", headers=user_headers).json()
    assert len(items) >= 1
    me = client.get("/api/auth/me", headers=user_headers).json()

    from app.models import Notification

    db = client.app.state.session_factory()
    try:
        user, pw = make_user(client)
        headers = auth_headers(client, user["email"], pw)
        uid = client.get("/api/auth/me", headers=headers).json()["id"]
        before = db.query(Notification).filter(Notification.user_id == uid).count()
        assert before >= 1
        client.request("DELETE", "/api/auth/me", json={"password": pw}, headers=headers)
        after = db.query(Notification).filter(Notification.user_id == uid).count()
        assert after == 0
    finally:
        db.close()
    assert me["id"]  # untouched user still fine
