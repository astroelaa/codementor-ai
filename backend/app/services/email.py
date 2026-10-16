"""Transactional email abstraction (verification + password reset only).

Three backends:
- console: logs recipient + subject to stdout (local dev). Never logs bodies
  containing links/tokens.
- smtp: real delivery through any SMTP provider via stdlib smtplib.
- resend: real delivery via the Resend HTTP API (needs RESEND_API_KEY).

All secrets (SMTP credentials, Resend key) stay server-side. Tests use an
in-memory backend injected through the FastAPI dependency below.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

import httpx
from fastapi import Request

from app.config import Settings

log = logging.getLogger("codementor.email")


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    text: str


class EmailBackend:
    def send(self, email: OutgoingEmail) -> None:
        raise NotImplementedError


class ConsoleEmailBackend(EmailBackend):
    def send(self, email: OutgoingEmail) -> None:
        # Recipient + subject only: bodies carry single-use links.
        log.info("email to=%s subject=%s", email.to, email.subject)


class SmtpEmailBackend(EmailBackend):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, email: OutgoingEmail) -> None:
        message = EmailMessage()
        message["From"] = self.settings.email_sender
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.text)
        try:
            with smtplib.SMTP(
                self.settings.email_smtp_host,
                self.settings.email_smtp_port,
                timeout=20,
            ) as smtp:
                smtp.starttls()
                if self.settings.email_smtp_user:
                    smtp.login(
                        self.settings.email_smtp_user,
                        self.settings.email_smtp_password,
                    )
                smtp.send_message(message)
        except Exception as exc:
            # Server reply codes and status messages are safe to log; they
            # never contain the password. Callers still get a generic 502.
            log.error(
                "email send failed to=%s host=%s class=%s detail=%s",
                email.to,
                self.settings.email_smtp_host,
                type(exc).__name__,
                str(exc)[:300],
            )
            raise


class MemoryEmailBackend(EmailBackend):
    """Test double: records what would have been sent."""

    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []

    def send(self, email: OutgoingEmail) -> None:
        self.sent.append(email)


class ResendEmailBackend(EmailBackend):
    """Real delivery through the Resend HTTP API.

    Non-2xx responses raise (via raise_for_status) so callers observe the
    failure and can map it to a 502 instead of claiming the mail went out.
    """

    RESEND_URL = "https://api.resend.com/emails"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, email: OutgoingEmail) -> None:
        response = httpx.post(
            self.RESEND_URL,
            headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
            json={
                "from": self.settings.email_sender,
                "to": [email.to],
                "subject": email.subject,
                "text": email.text,
            },
            timeout=20,
        )
        response.raise_for_status()


def build_backend(settings: Settings) -> EmailBackend:
    provider = settings.email_provider.strip().lower()
    if provider == "smtp":
        if not settings.email_smtp_host:
            raise RuntimeError("EMAIL_SMTP_HOST is required for the smtp provider")
        return SmtpEmailBackend(settings)
    if provider == "resend":
        if not settings.resend_api_key:
            raise RuntimeError("RESEND_API_KEY is required for the resend provider")
        return ResendEmailBackend(settings)
    return ConsoleEmailBackend()


def is_delivery_configured(settings: Settings) -> bool:
    """True when the provider has every credential it needs to send.

    This is a configuration check only — it cannot prove a live send. It
    exists so /health does not claim delivery when, e.g., the SMTP password
    is missing. smtp: host required; password required whenever a username
    is set (authenticated relays). resend: API key required. console and
    unknown providers never deliver.
    """
    provider = settings.email_provider.strip().lower()
    if provider == "smtp":
        if not settings.email_smtp_host:
            return False
        if settings.email_smtp_user and not settings.email_smtp_password:
            return False
        return True
    if provider == "resend":
        return bool(settings.resend_api_key)
    return False  # console and anything unknown only log


def get_email_backend(request: Request) -> EmailBackend:
    backend = getattr(request.app.state, "email_backend", None)
    if backend is None:
        backend = build_backend(request.app.state.settings)
        request.app.state.email_backend = backend
    return backend


BRAND = "CodeMentor AI"


def verification_email(to: str, link: str) -> OutgoingEmail:
    return OutgoingEmail(
        to=to,
        subject=f"{BRAND} — verify your email",
        text=(
            f"Welcome to {BRAND}!\n\n"
            "Please verify your email address by opening this link "
            f"(valid 24 hours, single use):\n\n{link}\n\n"
            "If you did not create this account, just ignore this message.\n"
        ),
    )


def reset_email(to: str, link: str) -> OutgoingEmail:
    return OutgoingEmail(
        to=to,
        subject=f"{BRAND} — password reset",
        text=(
            f"You asked to reset your {BRAND} password.\n\n"
            "Open this link to choose a new one "
            f"(valid 1 hour, single use):\n\n{link}\n\n"
            "If you did not ask for this, just ignore this message — "
            "your password stays unchanged.\n"
        ),
    )


def password_changed_email(to: str) -> OutgoingEmail:
    return OutgoingEmail(
        to=to,
        subject=f"{BRAND} — your password was changed",
        text=(
            f"The password for your {BRAND} account was just changed.\n\n"
            "If this was you, nothing to do. If not, request a reset "
            "immediately and contact support.\n"
        ),
    )


def solve_congrats_email(to: str, language: str, score: int) -> OutgoingEmail:
    return OutgoingEmail(
        to=to,
        subject=f"{BRAND} — session solved",
        text=(
            f"You solved a {language} debugging session with an explanation "
            f"score of {score}/100 — explained in your own words.\n\n"
            "Your dashboard has the updated streak and badges.\n"
        ),
    )
