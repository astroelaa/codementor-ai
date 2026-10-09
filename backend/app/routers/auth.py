"""Authentication routes: signup, login, profile, delete account."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.models import User
from app.rate_limit import limit
from app.schemas import (
    LoginRequest,
    PasswordBody,
    SignupRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.security import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_token(user: User, request: Request) -> TokenResponse:
    settings = request.app.state.settings
    token = create_access_token(
        user.id,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expire_days=settings.jwt_expire_days,
    )
    return TokenResponse(access_token=token)


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=201,
    dependencies=[limit("signup")],
)
def signup(payload: SignupRequest, request: Request, db: DbSession = Depends(deps.get_db)):
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
