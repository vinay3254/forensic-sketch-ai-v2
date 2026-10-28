from fastapi import Depends, Request
from sqlmodel import Session

from backend.auth.security import decode_token
from backend.db import get_session
from backend.errors import AppError
from backend.models import User

COOKIE_NAME = "session"


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise AppError("UNAUTHENTICATED", "Please log in.", 401)
    claims = decode_token(token, request.app.state.settings)
    user = session.get(User, int(claims["sub"]))
    if user is None:
        raise AppError("UNAUTHENTICATED", "Please log in.", 401)
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise AppError("FORBIDDEN", "You do not have permission for this action.", 403)
        return user

    return dep
