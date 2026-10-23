"""Supabase RLS isolation proof: backend API and PostgREST."""

import uuid
from datetime import datetime, timezone

import httpx

from tests.conftest import (
    PYTHON_CODE,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    admin_delete_user,
    admin_get_user,
    auth_headers,
    client,
    make_guest,
    make_user,
)


def _bearer(headers: dict[str, str]) -> str:
    scheme, _, token = headers["Authorization"].partition(" ")
    assert scheme.lower() == "bearer"
    assert token
    return token


def _rest(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    prefer: str | None = None,
) -> httpx.Response:
    headers = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if prefer:
        headers["Prefer"] = prefer
    with httpx.Client(timeout=30) as http:
        return http.request(
            method,
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers=headers,
            json=payload,
        )


def _project(user_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": "RLS isolation project",
        "objective": "Prove cross-user isolation",
        "language": "python",
        "stack": "pytest",
        "architecture": "PostgREST",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }


def _create_backend_project(headers: dict[str, str]) -> str:
    response = client.post(
        "/api/projects",
        json={
            "title": "Backend isolation project",
            "objective": "Prove ownership filters",
            "language": "python",
            "stack": "pytest",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_backend_session(
    headers: dict[str, str], project_id: str | None = None
) -> str:
    body = {"language": "python", "code": PYTHON_CODE}
    if project_id:
        body["project_id"] = project_id
    response = client.post("/api/sessions", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_backend_isolates_registered_users_and_guests():
    user_a, password_a = make_user(client, name="Alice")
    user_b, password_b = make_user(client, name="Bob")
    headers_a = auth_headers(client, user_a["email"], password_a)
    headers_b = auth_headers(client, user_b["email"], password_b)
    guest, guest_headers = make_guest(client)

    me_a = client.get("/api/auth/me", headers=headers_a)
    me_b = client.get("/api/auth/me", headers=headers_b)
    assert me_a.status_code == 200 and me_b.status_code == 200
    assert me_a.json()["id"] == user_a["id"]
    assert me_b.json()["id"] == user_b["id"]
    assert me_a.json()["is_anonymous"] is False
    assert me_b.json()["is_anonymous"] is False

    project_a = _create_backend_project(headers_a)
    project_b = _create_backend_project(headers_b)
    session_a = _create_backend_session(headers_a, project_a)
    session_b = _create_backend_session(headers_b, project_b)

    assert client.get(f"/api/sessions/{session_a}", headers=headers_a).status_code == 200
    assert client.get(f"/api/projects/{project_a}", headers=headers_a).status_code == 200
    assert client.get(f"/api/sessions/{session_b}", headers=headers_b).status_code == 200
    assert client.get(f"/api/projects/{project_b}", headers=headers_b).status_code == 200

    assert client.get(f"/api/sessions/{session_a}", headers=headers_b).status_code == 403
    assert (
        client.post(
            f"/api/sessions/{session_a}/messages",
            json={"content": "Show me the code."},
            headers=headers_b,
        ).status_code
        == 403
    )
    assert client.get(f"/api/projects/{project_a}", headers=headers_b).status_code == 404
    assert (
        client.patch(
            f"/api/projects/{project_a}",
            json={"title": "Hijacked"},
            headers=headers_b,
        ).status_code
        == 404
    )

    sessions_a = {row["id"] for row in client.get("/api/sessions", headers=headers_a).json()}
    sessions_b = {row["id"] for row in client.get("/api/sessions", headers=headers_b).json()}
    projects_a = {row["id"] for row in client.get("/api/projects", headers=headers_a).json()}
    projects_b = {row["id"] for row in client.get("/api/projects", headers=headers_b).json()}
    assert session_a in sessions_a and session_b not in sessions_a
    assert session_b in sessions_b and session_a not in sessions_b
    assert project_a in projects_a and project_b not in projects_a
    assert project_b in projects_b and project_a not in projects_b

    guest_me = client.get("/api/auth/me", headers=guest_headers)
    assert guest_me.status_code == 200
    assert guest_me.json()["id"] == guest["id"]
    assert guest_me.json()["is_anonymous"] is True
    assert client.get(f"/api/sessions/{session_a}", headers=guest_headers).status_code == 403
    assert client.get(f"/api/projects/{project_a}", headers=guest_headers).status_code == 404
    assert session_a not in {
        row["id"] for row in client.get("/api/sessions", headers=guest_headers).json()
    }
    assert project_a not in {
        row["id"] for row in client.get("/api/projects", headers=guest_headers).json()
    }

    assert client.get(f"/api/sessions/{session_a}").status_code == 401
    assert client.get("/api/sessions").status_code == 401


def test_supabase_rest_rls_isolates_users_projects_and_guests():
    user_a, password_a = make_user(client, name="Rest Alice")
    user_b, password_b = make_user(client, name="Rest Bob")
    guest, guest_headers = make_guest(client)
    token_a = _bearer(auth_headers(client, user_a["email"], password_a))
    token_b = _bearer(auth_headers(client, user_b["email"], password_b))
    token_guest = _bearer(guest_headers)

    rows_a = _rest("GET", "users?select=id,email", token=token_a)
    rows_b = _rest("GET", "users?select=id,email", token=token_b)
    rows_guest = _rest("GET", "users?select=id,email", token=token_guest)
    assert rows_a.status_code == 200, rows_a.text
    assert rows_b.status_code == 200, rows_b.text
    assert rows_guest.status_code == 200, rows_guest.text
    assert rows_a.json() == [{"id": user_a["id"], "email": user_a["email"]}]
    assert rows_b.json() == [{"id": user_b["id"], "email": user_b["email"]}]
    assert rows_guest.json() == [{"id": guest["id"], "email": None}]

    anon_users = _rest("GET", "users?select=id")
    assert anon_users.status_code in (401, 403) or anon_users.json() == []

    project = _project(user_a["id"])
    created = _rest(
        "POST",
        "projects",
        token=token_a,
        payload=project,
        prefer="return=representation",
    )
    assert created.status_code == 201, created.text
    assert created.json()[0]["id"] == project["id"]

    own = _rest(
        "GET",
        f"projects?select=id,title,user_id&id=eq.{project['id']}",
        token=token_a,
    )
    other = _rest(
        "GET",
        f"projects?select=id,title,user_id&id=eq.{project['id']}",
        token=token_b,
    )
    guest_view = _rest(
        "GET",
        f"projects?select=id,title,user_id&id=eq.{project['id']}",
        token=token_guest,
    )
    anon_view = _rest("GET", f"projects?select=id&id=eq.{project['id']}")
    assert own.status_code == 200 and own.json()[0]["id"] == project["id"]
    assert other.status_code == 200 and other.json() == []
    assert guest_view.status_code == 200 and guest_view.json() == []
    assert anon_view.status_code in (401, 403) or anon_view.json() == []

    forged = _rest(
        "POST",
        "projects",
        token=token_b,
        payload=_project(user_a["id"]),
    )
    assert forged.status_code == 403, forged.text

    hijack = _rest(
        "PATCH",
        f"projects?id=eq.{project['id']}",
        token=token_b,
        payload={"title": "Hijacked"},
        prefer="return=representation",
    )
    assert hijack.status_code in (200, 204)
    if hijack.status_code == 200:
        assert hijack.json() == []
    still_own = _rest(
        "GET",
        f"projects?select=title&id=eq.{project['id']}",
        token=token_a,
    )
    assert still_own.json() == [{"title": project["title"]}]

    stolen_delete = _rest(
        "DELETE",
        f"projects?id=eq.{project['id']}",
        token=token_b,
    )
    assert stolen_delete.status_code in (200, 204)
    assert _rest(
        "GET",
        f"projects?select=id&id=eq.{project['id']}",
        token=token_a,
    ).json() == [{"id": project["id"]}]

    profile_hijack = _rest(
        "PATCH",
        f"users?id=eq.{user_a['id']}",
        token=token_b,
        payload={"display_name": "Hijacked"},
        prefer="return=representation",
    )
    assert profile_hijack.status_code in (200, 204)
    profile = _rest(
        "GET",
        f"users?select=display_name&id=eq.{user_a['id']}",
        token=token_a,
    )
    assert profile.json() == [{"display_name": user_a["display_name"]}]

    owner_delete = _rest(
        "DELETE",
        f"projects?id=eq.{project['id']}",
        token=token_a,
    )
    assert owner_delete.status_code in (200, 204)
    assert _rest(
        "GET",
        f"projects?select=id&id=eq.{project['id']}",
        token=token_a,
    ).json() == []


def test_cleanup_removes_test_users():
    user, _ = make_user(client, name="Cleanup")
    assert admin_get_user(user["id"]) is not None
    admin_delete_user(user["id"])
    assert admin_get_user(user["id"]) is None
