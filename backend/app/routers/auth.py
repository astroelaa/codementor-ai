"""Authentication routes: signup, login, profile, delete account,
email verification, and password recovery."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.models import AuthToken, User
from app.rate_limit import limit
from app.schemas import (
    EmailRequest,
    LoginRequest,
    MessageResponse,
    PasswordBody,
    ResetPasswordRequest,
    SignupRequest,
    TokenBody,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_raw_token,
    verify_password,
)
from app.services.email import (
    ConsoleEmailBackend,
    EmailBackend,
    get_email_backend,
    password_changed_email,
    reset_email,
    verification_email,
)
from app.services.notifications import notify

router = APIRouter(prefix="/api/auth", tags=["auth"])

VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(hours=1)
RESEND_PER_HOUR = 3


def _issue_token(user: User, request: Request) -> TokenResponse:
    settings = request.app.state.settings
    token = create_access_token(
        user.id,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expire_days=settings.jwt_expire_days,
        version=user.token_version,
    )
    return TokenResponse(access_token=token)


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=201,
    dependencies=[limit("signup")],
)
def signup(
    payload: SignupRequest,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    mailer: EmailBackend = Depends(get_email_backend),
):
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    raw = _issue_email_token(db, user, "verify_email", VERIFY_TTL)
    try:
        mailer.send(
            verification_email(user.email, _verification_link(request, raw))
        )
    except Exception:
        pass  # signup still succeeds; the banner offers a resend
    notify(
        db,
        user.id,
        "welcome",
        "Welcome to CodeMentor AI",
        "Verify your email to protect your account, then start your first debugging session.",
    )
    db.commit()
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[limit("login")],
)
def login(payload: LoginRequest, request: Request, db: DbSession = Depends(deps.get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")
    return _issue_token(user, request)


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
    db.commit()
    db.refresh(user)
    return user


@router.delete("/me", status_code=204)
def delete_account(
    payload: PasswordBody,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong password.")
    db.delete(user)  # cascades to sessions, messages, badges, activity, ...
    db.commit()
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue_email_token(db: DbSession, user: User, purpose: str, ttl: timedelta) -> str:
    raw = new_raw_token()
    db.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=_now() + ttl,
        )
    )
    db.commit()
    return raw


def _verification_link(request: Request, raw: str) -> str:
    base = request.app.state.settings.frontend_url.rstrip("/")
    return f"{base}/#/verify?token={raw}"


def _reset_link(request: Request, raw: str) -> str:
    base = request.app.state.settings.frontend_url.rstrip("/")
    return f"{base}/#/reset?token={raw}"


def _lookup_token(db: DbSession, raw: str, purpose: str) -> AuthToken | None:
    """Find a live token by its hash. Returns None for missing, used, or
    expired tokens alike, so callers cannot distinguish the cases."""
    record = (
        db.query(AuthToken)
        .filter(
            AuthToken.token_hash == hash_token(raw),
            AuthToken.purpose == purpose,
        )
        .first()
    )
    if record is None or record.used_at is not None:
        return None
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= _now():
        return None
    return record


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    dependencies=[limit("login")],
)
def resend_verification(
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
    mailer: EmailBackend = Depends(get_email_backend),
):
    if user.is_verified:
        return MessageResponse(message="Email already verified.")
    if isinstance(mailer, ConsoleEmailBackend):
        raise HTTPException(
            status_code=501,
            detail="Email delivery is not configured on this server. Contact support.",
        )
    recent = (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user.id,
            AuthToken.purpose == "verify_email",
            AuthToken.created_at >= _now() - timedelta(hours=1),
        )
        .count()
    )
    if recent >= RESEND_PER_HOUR:
        raise HTTPException(
            status_code=429, detail="Too many requests. Try again later."
        )
    raw = _issue_email_token(db, user, "verify_email", VERIFY_TTL)
    try:
        mailer.send(
            verification_email(user.email, _verification_link(request, raw))
        )
    except Exception:
        raise HTTPException(
            status_code=502, detail="Could not send the email. Try again later."
        )
    return MessageResponse(message="Verification email sent.")


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[limit("login")],
)
def verify_email(payload: TokenBody, db: DbSession = Depends(deps.get_db)):
    record = _lookup_token(db, payload.token.strip(), "verify_email")
    if record is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification link."
        )
    user = db.query(User).filter(User.id == record.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification link."
        )
    user.is_verified = True
    record.used_at = _now()
    db.commit()
    return MessageResponse(message="Email verified. Welcome aboard.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[limit("login")],
)
def forgot_password(
    payload: EmailRequest,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    mailer: EmailBackend = Depends(get_email_backend),
):
    # Generic response always: never reveal whether the address exists.
    user = (
        db.query(User)
        .filter(User.email == payload.email.strip().lower())
        .first()
    )
    if user is not None:
        db.query(AuthToken).filter(
            AuthToken.user_id == user.id,
            AuthToken.purpose == "reset_password",
            AuthToken.used_at.is_(None),
        ).update({"used_at": _now()})
        raw = _issue_email_token(db, user, "reset_password", RESET_TTL)
        try:
            mailer.send(reset_email(user.email, _reset_link(request, raw)))
        except Exception:
            pass  # keep the response generic; the token simply won't arrive
    return MessageResponse(
        message="If an account exists for this email, a reset link is on its way."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[limit("login")],
)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    mailer: EmailBackend = Depends(get_email_backend),
):
    record = _lookup_token(db, payload.token.strip(), "reset_password")
    if record is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired reset link."
        )
    user = db.query(User).filter(User.id == record.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired reset link."
        )
    user.password_hash = hash_password(payload.new_password)
    user.token_version = (user.token_version or 0) + 1  # revoke all sessions
    record.used_at = _now()
    db.commit()
    try:
        mailer.send(password_changed_email(user.email))
    except Exception:
        pass  # reset already succeeded; notice is best-effort
    return MessageResponse(message="Password reset. Please log in again.")
