"""Password hashing (bcrypt), JWT access tokens, and single-use token helpers."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str, *, secret: str, algorithm: str, expire_days: int,
    version: int = 0,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "ver": version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=expire_days)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token_subject(token: str, *, secret: str, algorithms: list[str]) -> str:
    """Return the token subject, or raise ValueError when invalid/expired."""
    return decode_token(token, secret=secret, algorithms=algorithms)["sub"]


def decode_token(token: str, *, secret: str, algorithms: list[str]) -> dict:
    """Return the full JWT payload, or raise ValueError when invalid/expired."""
    try:
        payload = jwt.decode(token, secret, algorithms=algorithms)
    except jwt.PyJWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc
    subject = payload.get("sub")
    if not subject:
        raise ValueError("token has no subject")
    payload["sub"] = str(subject)
    return payload


def new_raw_token() -> str:
    """Cryptographically secure token for email links (shown once)."""
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    """SHA-256 hash for storage — the raw value is never persisted."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
