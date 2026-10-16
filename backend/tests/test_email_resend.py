"""Resend email provider tests (httpx mocked, no network)."""

import httpx
import pytest

from app.config import Settings
from app.services import email as email_module
from app.services.email import (
    ConsoleEmailBackend,
    EmailBackend,
    MemoryEmailBackend,
    OutgoingEmail,
    ResendEmailBackend,
    build_backend,
    get_email_backend,
)
from tests.conftest import auth_headers, client, make_user


def _settings(**overrides):
    base = {
        "email_provider": "resend",
        "email_sender": "CodeMentor AI <verify@example.com>",
        "resend_api_key": "re_test_sentinel",
    }
    base.update(overrides)
    return Settings(**base)


def test_resend_backend_success_posts_expected_payload(monkeypatch):
    seen = {}

    def fake_post(url, *, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(200, request=httpx.Request("POST", url), json={"id": "re_test_id"})

    monkeypatch.setattr(email_module.httpx, "post", fake_post)
    ResendEmailBackend(_settings()).send(
        OutgoingEmail(to="u@example.com", subject="S", text="body")
    )
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"]["Authorization"].startswith("Bearer ")
    assert seen["json"]["from"] == "CodeMentor AI <verify@example.com>"
    assert seen["json"]["to"] == ["u@example.com"]
    assert seen["json"]["subject"] == "S"
    assert seen["json"]["text"] == "body"


def test_resend_backend_failure_raises(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        request = httpx.Request("POST", url)
        return httpx.Response(422, request=request, json={"message": "bad from"})

    monkeypatch.setattr(email_module.httpx, "post", fake_post)
    with pytest.raises(httpx.HTTPStatusError):
        ResendEmailBackend(_settings()).send(
            OutgoingEmail(to="u@example.com", subject="S", text="body")
        )


def test_build_backend_selection():
    assert isinstance(build_backend(_settings()), ResendEmailBackend)
    assert isinstance(build_backend(_settings(email_provider="console")), ConsoleEmailBackend)
    with pytest.raises(RuntimeError):
        build_backend(_settings(resend_api_key=""))


def _override(mem):
    client.app.dependency_overrides[get_email_backend] = lambda: mem


def _teardown():
    client.app.dependency_overrides.pop(get_email_backend, None)


def test_signup_sends_one_verification_email():
    mem = MemoryEmailBackend()
    _override(mem)
    try:
        user, password = make_user(client)
        assert len(mem.sent) == 1
        assert "verify" in mem.sent[0].subject.lower()
        assert user["email"] in mem.sent[0].to
        raw = mem.sent[0].text.split("token=")[1].split()[0]
        r = client.post("/api/auth/verify-email", json={"token": raw})
        assert r.status_code == 200, r.text
    finally:
        _teardown()


class _FailingBackend(EmailBackend):
    def send(self, email: OutgoingEmail) -> None:
        raise RuntimeError("provider down")


def test_provider_failure_signup_still_201_but_resend_502():
    _override(_FailingBackend())
    try:
        # Send failure must not fail signup.
        r = client.post(
            "/api/auth/signup",
            json={"email": "resend-fail@example.com", "password": "secret123", "display_name": "RF"},
        )
        assert r.status_code == 201, r.text
        headers = auth_headers(client, "resend-fail@example.com", "secret123")
        r = client.post("/api/auth/resend-verification", headers=headers)
        assert r.status_code == 502, r.text
    finally:
        _teardown()
