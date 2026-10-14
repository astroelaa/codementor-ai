"""Transactional email abstraction (verification + password reset only).

Two backends, no new dependencies:
- console: logs recipient + subject to stdout (local dev). Never logs bodies
  containing links/tokens.
- smtp: real delivery through any SMTP provider via stdlib smtplib.

All secrets (SMTP credentials) stay server-side. Tests use an in-memory
backend injected through the FastAPI dependency below.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

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
        with smtplib.SMTP(
            self.settings.email_smtp_host, self.settings.email_smtp_port, timeout=20
        ) as smtp:
            smtp.starttls()
            if self.settings.email_smtp_user:
                smtp.login(
                    self.settings.email_smtp_user, self.settings.email_smtp_password
                )
            smtp.send_message(message)


class MemoryEmailBackend(EmailBackend):
    """Test double: records what would have been sent."""

    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []

    def send(self, email: OutgoingEmail) -> None:
        self.sent.append(email)


def build_backend(settings: Settings) -> EmailBackend:
    if settings.email_provider.strip().lower() == "smtp":
        if not settings.email_smtp_host:
            raise RuntimeError("EMAIL_SMTP_HOST is required for the smtp provider")
        return SmtpEmailBackend(settings)
    return ConsoleEmailBackend()


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
