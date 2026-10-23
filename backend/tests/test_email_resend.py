"""Resend email provider tests (httpx mocked, no network)."""

import httpx
import pytest

from app.config import Settings
from app.services import email as email_module
from app.services.email import (
    ConsoleEmailBackend,
    OutgoingEmail,
    ResendEmailBackend,
    build_backend,
    is_delivery_configured,
)
from tests.conftest import client


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


def test_health_reports_email_delivery_flag():
    r = client.get("/health")
    assert r.status_code == 200, r.text
    # Conftest settings use the console default: nothing really sends.
    assert r.json()["email_delivery"] is False


def test_is_delivery_configured_cases():
    assert is_delivery_configured(Settings(email_provider="console")) is False
    assert is_delivery_configured(Settings(email_provider="resend", resend_api_key="k")) is True
    assert is_delivery_configured(Settings(email_provider="resend")) is False
    # smtp: host always required; password required when a username is set
    assert is_delivery_configured(Settings(email_provider="smtp", email_smtp_host="h")) is True
    assert is_delivery_configured(Settings(email_provider="smtp")) is False
    assert (
        is_delivery_configured(
            Settings(email_provider="smtp", email_smtp_host="h", email_smtp_user="u")
        )
        is False
    )
    assert (
        is_delivery_configured(
            Settings(
                email_provider="smtp",
                email_smtp_host="h",
                email_smtp_user="u",
                email_smtp_password="pw",
            )
        )
        is True
    )
