"""Request dependencies: database session, LLM manager, Supabase identity."""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy import event, text
from sqlalchemy.orm import Session as DbSession

from app.llm.manager import LLMManager
from app.models import User
from app.supabase_auth import (
    AuthContext,
    AuthUnavailableError,
    InvalidTokenError,
    verify_access_token,
)


def _bearer_token(request: Request) -> str | None:
    value = request.headers.get("Authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def get_auth_context(request: Request) -> AuthContext | None:
    token = _bearer_token(request)
    if token is None:
        request.state.auth = None
        return None
    client = request.app.state.jwks_client
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured on this server.",
        )
    settings = request.app.state.settings
    issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1"
    try:
        context = verify_access_token(token, jwks_client=client, issuer=issuer)
    except AuthUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="Authentication is temporarily unavailable.",
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.auth = context
    return context


def get_db(
    request: Request,
    auth: AuthContext | None = Depends(get_auth_context),
) -> Iterator[DbSession]:
    db = request.app.state.session_factory()
    role = "authenticated" if auth is not None else "anon"
    claims = json.dumps(auth.claims if auth is not None else {}, separators=(",", ":"))

    @event.listens_for(db, "after_begin")
    def _apply_rls(session, transaction, connection):
        if connection.dialect.name != "postgresql":
            return
        connection.execute(text(f"SET LOCAL ROLE {role}"))
        connection.execute(
            text("SELECT set_config('request.jwt.claims', :claims, true)"),
            {"claims": claims},
        )

    try:
        yield db
    finally:
        db.close()


def get_llm_manager(request: Request) -> LLMManager:
    return request.app.state.llm_manager


def get_current_user(
    db: DbSession = Depends(get_db),
    auth: AuthContext | None = Depends(get_auth_context),
) -> User:
    if auth is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == auth.user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user.is_anonymous = auth.is_anonymous
    return user
