"""Supabase access-token verification and identity administration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from app.config import Settings


class InvalidTokenError(Exception):
    pass


class AuthUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: str | None
    is_anonymous: bool
    claims: dict[str, Any]


def _auth_base(settings: Settings) -> str:
    return settings.supabase_url.rstrip("/")


def build_jwks_client(settings: Settings) -> PyJWKClient | None:
    base = _auth_base(settings)
    if not base:
        return None
    return PyJWKClient(
        f"{base}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
        lifespan=300,
        timeout=10,
    )


def verify_access_token(
    token: str,
    *,
    jwks_client: PyJWKClient,
    issuer: str,
) -> AuthContext:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except PyJWKClientConnectionError as exc:
        raise AuthUnavailableError("JWKS is unavailable") from exc
    except (PyJWKClientError, jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError("Invalid or expired token") from exc

    subject = str(claims.get("sub") or "").strip()
    if not subject or claims.get("role") != "authenticated":
        raise InvalidTokenError("Invalid or expired token")
    return AuthContext(
        user_id=subject,
        email=claims.get("email") or None,
        is_anonymous=bool(claims.get("is_anonymous", False)),
        claims=claims,
    )


def delete_auth_user(settings: Settings, user_id: str) -> None:
    base = _auth_base(settings)
    service_key = settings.supabase_service_role_key
    if not base or not service_key:
        raise AuthUnavailableError("Supabase admin is not configured")
    try:
        response = httpx.delete(
            f"{base}/auth/v1/admin/users/{user_id}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise AuthUnavailableError("Supabase admin is unavailable") from exc
    if response.status_code == 404:
        return
    if response.status_code >= 400:
        raise AuthUnavailableError("Supabase admin rejected the request")
