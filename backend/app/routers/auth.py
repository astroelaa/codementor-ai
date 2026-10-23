"""Supabase-backed profile routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.models import User
from app.schemas import (
    EXPERIENCE_LEVELS,
    LEARNING_GOALS,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.languages import supported_keys
from app.supabase_auth import AuthUnavailableError, delete_auth_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _valid_language(key: str) -> bool:
    if key == "":
        return True
    return key in supported_keys()


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(deps.get_current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
def update_profile(
    payload: UpdateProfileRequest,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.theme is not None:
        user.theme = payload.theme
    if payload.notify_security_emails is not None:
        user.notify_security_emails = payload.notify_security_emails
    if payload.notify_progress_emails is not None:
        user.notify_progress_emails = payload.notify_progress_emails
    if payload.preferred_language is not None:
        if not _valid_language(payload.preferred_language):
            raise HTTPException(
                status_code=422,
                detail="Unknown language. Choose one of the supported languages.",
            )
        user.preferred_language = payload.preferred_language
    if payload.experience_level is not None:
        if payload.experience_level not in ("", *EXPERIENCE_LEVELS):
            raise HTTPException(
                status_code=422, detail="Unsupported experience level."
            )
        user.experience_level = payload.experience_level
    if payload.learning_goal is not None:
        if payload.learning_goal not in ("", *LEARNING_GOALS):
            raise HTTPException(status_code=422, detail="Unsupported learning goal.")
        user.learning_goal = payload.learning_goal
    db.commit()
    db.refresh(user)
    return user


@router.delete("/me", status_code=204)
def delete_account(
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    try:
        delete_auth_user(request.app.state.settings, user.id)
    except AuthUnavailableError:
        raise HTTPException(
            status_code=502,
            detail="Could not delete the account. Try again.",
        )
    db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
    db.commit()
    return None
