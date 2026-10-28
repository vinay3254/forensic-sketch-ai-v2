from fastapi import Depends, Request
from sqlmodel import Session

from backend.audit.logger import record
from backend.auth.security import decode_token
from backend.db import get_session
from backend.errors import AppError
from backend.models import Case, User

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


def require_case_access(
    case_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Case:
    case = session.get(Case, case_id)
    if case is None:
        raise AppError("NOT_FOUND", "Case not found.", 404)
    if user.role != "admin" and case.created_by != user.id:
        record(session, request, "access_denied", user, case_id=case_id)
        raise AppError("FORBIDDEN", "You do not have access to this case.", 403)
    return case
