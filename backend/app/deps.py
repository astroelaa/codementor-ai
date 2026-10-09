"""Request dependencies: database session, LLM manager, auth."""

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from app.config import Settings
from app.llm.manager import LLMManager
from app.models import User
from app.security import decode_token_subject

GUEST_TOKEN_HEADER = "X-Guest-Token"


def get_db(request: Request):
    factory = request.app.state.session_factory
    db = factory()
    try:
        yield db
    finally:
        db.close()


def get_llm_manager(request: Request) -> LLMManager:
    return request.app.state.llm_manager


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


def guest_token_from(request: Request) -> str | None:
    token = request.headers.get(GUEST_TOKEN_HEADER)
    return token.strip() if token and token.strip() else None


def new_guest_token() -> str:
    return str(uuid.uuid4())


def get_optional_user(
    request: Request, db: DbSession = Depends(get_db)
) -> User | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    settings: Settings = request.app.state.settings
    try:
        subject = decode_token_subject(
            auth[7:].strip(),
            secret=settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except ValueError:
        raise HTTPException(
            status_code=401, detail="Invalid or expired token."
        )
    user = (
        db.query(User)
        .filter(User.id == subject, User.is_active == True)  # noqa: E712
        .first()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


def get_current_user(
    request: Request, db: DbSession = Depends(get_db)
) -> User:
    user = get_optional_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user
