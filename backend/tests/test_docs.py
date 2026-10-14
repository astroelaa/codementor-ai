"""Doc simplifier tests: validation, persistence, isolation."""

from tests.conftest import auth_headers, client, fake_llm, make_user, user_headers  # noqa: F401
from tests.fake_llm import DOC_JSON

TEXT = "A list comprehension builds a new list by applying an expression to each item."


def test_simplify_requires_auth():
    r = client.post("/api/docs/simplify", json={"text": TEXT})
    assert r.status_code == 401


def test_simplify_validation(user_headers):
    r = client.post("/api/docs/simplify", json={"text": ""}, headers=user_headers)
    assert r.status_code == 422
    r = client.post(
        "/api/docs/simplify", json={"text": "x" * 4001}, headers=user_headers
    )
    assert r.status_code == 422


def test_simplify_success_and_history(user_headers, fake_llm):
    fake_llm.queue_complete(DOC_JSON)
    r = client.post(
        "/api/docs/simplify",
        json={"text": TEXT, "language": "python"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "list comprehension" in body["explanation"]
    assert body["example"]
    assert body["question"]
    assert body["id"]

    r = client.get("/api/docs/history", headers=user_headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["input_text"] == TEXT
    assert items[0]["explanation"] == body["explanation"]


def test_history_isolated_per_user(user_headers, fake_llm):
    fake_llm.queue_complete(DOC_JSON)
    client.post("/api/docs/simplify", json={"text": TEXT}, headers=user_headers)

    other, pw = make_user(client)
    other_headers = auth_headers(client, other["email"], pw)
    r = client.get("/api/docs/history", headers=other_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_simplify_bad_model_json_is_502(user_headers, fake_llm):
    fake_llm.queue_complete("not json at all")
    r = client.post("/api/docs/simplify", json={"text": TEXT}, headers=user_headers)
    assert r.status_code == 502
