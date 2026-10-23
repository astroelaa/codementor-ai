"""Project briefs, milestones, tasks: persistence, ownership, progression."""

from tests.conftest import auth_headers, client, make_guest, make_user
from tests.fake_llm import BRIEF_JSON


def _make_project(headers, **overrides):
    body = {"title": "Todo CLI", "objective": "", "language": "python", "stack": ""}
    body.update(overrides)
    r = client.post("/api/projects", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_project_crud_and_validation(user_headers):
    p = _make_project(user_headers)
    assert p["status"] == "active"
    assert p["milestones"] == []

    r = client.post(
        "/api/projects",
        json={"title": "Bad", "language": "brainfuck"},
        headers=user_headers,
    )
    assert r.status_code == 422

    r = client.patch(
        f"/api/projects/{p['id']}",
        json={"status": "done", "stack": "stdlib only"},
        headers=user_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert r.json()["stack"] == "stdlib only"

    r = client.get("/api/projects", headers=user_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["milestone_count"] == 0


def test_projects_require_auth():
    assert client.post("/api/projects", json={"title": "x"}).status_code == 401
    assert client.get("/api/projects").status_code == 401


def test_brief_generates_and_stores_milestones(user_headers, fake_llm):
    p = _make_project(user_headers)
    fake_llm.queue_complete(BRIEF_JSON)
    r = client.post(
        f"/api/projects/{p['id']}/brief",
        json={"description": "A command-line todo app storing tasks in a JSON file."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    brief = r.json()
    assert "todo" in brief["objective"].lower()
    assert len(brief["milestones"]) == 2

    r = client.get(f"/api/projects/{p['id']}", headers=user_headers)
    detail = r.json()
    assert detail["objective"]
    assert detail["architecture"]
    assert len(detail["milestones"]) == 2
    assert len(detail["milestones"][0]["tasks"]) == 2


def test_brief_description_validated(user_headers):
    p = _make_project(user_headers)
    r = client.post(
        f"/api/projects/{p['id']}/brief",
        json={"description": "tiny"},
        headers=user_headers,
    )
    assert r.status_code == 422


def test_milestone_task_lifecycle_and_next(user_headers):
    p = _make_project(user_headers)
    r = client.post(
        f"/api/projects/{p['id']}/milestones",
        json={"title": "Storage", "detail": "file format"},
        headers=user_headers,
    )
    assert r.status_code == 201
    mid = r.json()["id"]

    for title in ("Design format", "Write save/load"):
        r = client.post(
            f"/api/projects/milestones/{mid}/tasks",
            json={"title": title},
            headers=user_headers,
        )
        assert r.status_code == 201, r.text
    tids = [t["id"] for t in client.get(f"/api/projects/{p['id']}", headers=user_headers).json()["milestones"][0]["tasks"]]
    assert len(tids) == 2

    r = client.get(f"/api/projects/{p['id']}/next", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["done"] is False
    assert r.json()["task"]["title"] == "Design format"

    client.patch(
        f"/api/projects/tasks/{tids[0]}", json={"status": "done"}, headers=user_headers
    )
    r = client.get(f"/api/projects/{p['id']}/next", headers=user_headers)
    assert r.json()["task"]["title"] == "Write save/load"

    client.patch(
        f"/api/projects/tasks/{tids[1]}", json={"status": "done"}, headers=user_headers
    )
    client.patch(
        f"/api/projects/milestones/{mid}", json={"status": "done"}, headers=user_headers
    )
    r = client.get(f"/api/projects/{p['id']}/next", headers=user_headers)
    assert r.json()["done"] is True

    r = client.patch(
        f"/api/projects/tasks/{tids[0]}", json={"status": "finished"}, headers=user_headers
    )
    assert r.status_code == 422


def test_project_ownership_isolated(user_headers):
    p = _make_project(user_headers)
    other, pw = make_user(client)
    other_headers = auth_headers(client, other["email"], pw)

    assert client.get(f"/api/projects/{p['id']}", headers=other_headers).status_code == 404
    assert client.patch(f"/api/projects/{p['id']}", json={"title": "Hijack"}, headers=other_headers).status_code == 404
    assert client.post(f"/api/projects/{p['id']}/brief", json={"description": "A long enough description here."}, headers=other_headers).status_code == 404
    assert client.post(f"/api/projects/{p['id']}/milestones", json={"title": "x"}, headers=other_headers).status_code == 404
    assert client.get(f"/api/projects/{p['id']}/next", headers=other_headers).status_code == 404

    r = client.post(
        f"/api/projects/{p['id']}/milestones",
        json={"title": "M"},
        headers=user_headers,
    )
    mid = r.json()["id"]
    r = client.post(
        f"/api/projects/milestones/{mid}/tasks",
        json={"title": "T"},
        headers=user_headers,
    )
    tid = r.json()["id"]
    assert client.patch(f"/api/projects/milestones/{mid}", json={"status": "done"}, headers=other_headers).status_code == 404
    assert client.patch(f"/api/projects/tasks/{tid}", json={"status": "done"}, headers=other_headers).status_code == 404


def test_session_project_link(user_headers):
    p = _make_project(user_headers)
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1", "project_id": p["id"]},
        headers=user_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["project_id"] == p["id"]

    other, pw = make_user(client)
    other_headers = auth_headers(client, other["email"], pw)
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1", "project_id": p["id"]},
        headers=other_headers,
    )
    assert r.status_code == 404

    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1", "project_id": "nope"},
        headers=user_headers,
    )
    assert r.status_code == 404


def test_guest_cannot_link_missing_project():
    _, headers = make_guest(client)
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1", "project_id": "whatever"},
        headers=headers,
    )
    assert r.status_code == 404
