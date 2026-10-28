from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.audit.logger import record
from backend.auth.deps import COOKIE_NAME, current_user
from backend.auth.security import create_token, verify_password
from backend.db import get_session
from backend.errors import AppError
from backend.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    role: str


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)):
    settings = request.app.state.settings
    limiter = request.app.state.login_limiter
    limiter.check(body.username)
    user = session.exec(select(User).where(User.username == body.username)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        limiter.fail(body.username)
        record(session, request, "login_failed", username=body.username)
        raise AppError("UNAUTHENTICATED", "Wrong username or password.", 401)
    limiter.reset(body.username)
    record(session, request, "login", user)
    response.set_cookie(
        COOKIE_NAME,
        create_token(user.id, user.role, settings),
        max_age=settings.jwt_expiry_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )
    return UserOut(id=user.id, username=user.username, role=user.role)


@router.post("/logout", status_code=204)
def logout(
    request: Request, response: Response, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    record(session, request, "logout", user)
    response.delete_cookie(COOKIE_NAME)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut(id=user.id, username=user.username, role=user.role)
