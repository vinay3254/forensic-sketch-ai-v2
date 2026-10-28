import hmac
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.audit.logger import record
from backend.auth.deps import COOKIE_NAME, current_user, session_claims
from backend.auth.security import DUMMY_HASH, create_token, hash_password, verify_password
from backend.db import get_session
from backend.errors import AppError
from backend.models import RevokedToken, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    role: str


def _start_session(response: Response, user: User, settings) -> UserOut:
    response.set_cookie(
        COOKIE_NAME,
        create_token(user.id, user.role, settings),
        max_age=settings.jwt_expiry_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )
    return UserOut(id=user.id, username=user.username, role=user.role)


class SignupIn(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,32}$")
    password: str = Field(min_length=8, max_length=200)
    role: Literal["officer", "admin"]
    admin_code: str | None = Field(default=None, max_length=200)


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(body: SignupIn, request: Request, response: Response, session: Session = Depends(get_session)):
    """Investigators create their own account. An admin account needs ADMIN_SIGNUP_CODE, so that not
    just anyone can read every investigator's activity; with no code set, admin sign-up is off."""
    settings = request.app.state.settings
    limiter = request.app.state.login_limiter
    key = f"signup:{request.client.host if request.client else ''}"
    limiter.check(key)
    if body.role == "admin":
        code = settings.admin_signup_code
        if not code:
            raise AppError("FORBIDDEN", "Admin sign-up is not enabled here. Ask an existing admin.", 403)
        if not hmac.compare_digest((body.admin_code or "").encode(), code.encode()):
            limiter.fail(key)
            raise AppError("FORBIDDEN", "That admin code is not right.", 403)
    if session.exec(select(User).where(User.username == body.username)).first():
        raise AppError("CONFLICT", "That username is taken.", 409)
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    session.add(user)
    session.commit()
    session.refresh(user)
    record(session, request, "signup", user, detail={"role": user.role})
    record(session, request, "login", user)
    return _start_session(response, user, settings)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)):
    settings = request.app.state.settings
    limiter = request.app.state.login_limiter
    limiter.check(body.username)
    user = session.exec(select(User).where(User.username == body.username)).first()
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not ok:
        limiter.fail(body.username)
        record(session, request, "login_failed", username=body.username)
        raise AppError("UNAUTHENTICATED", "Wrong username or password.", 401)
    limiter.reset(body.username)
    record(session, request, "login", user)
    return _start_session(response, user, settings)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    claims: dict = Depends(session_claims),
    session: Session = Depends(get_session),
):
    session.add(RevokedToken(jti=claims["jti"], expires_at=datetime.fromtimestamp(claims["exp"], UTC)))
    session.commit()
    record(session, request, "logout", user)
    response.delete_cookie(
        COOKIE_NAME, httponly=True, secure=request.app.state.settings.cookie_secure, samesite="strict"
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut(id=user.id, username=user.username, role=user.role)
