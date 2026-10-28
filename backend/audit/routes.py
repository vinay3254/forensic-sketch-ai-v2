from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlmodel import Session, select

from backend.audit.logger import record, verify_chain
from backend.auth.deps import require_role
from backend.db import get_session
from backend.models import AuditLog, User

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit(
    request: Request,
    case_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user: User = Depends(require_role("admin")),
    session: Session = Depends(get_session),
):
    filters = []
    if case_id is not None:
        filters.append(AuditLog.case_id == case_id)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if since:
        filters.append(AuditLog.ts >= since)
    if until:
        filters.append(AuditLog.ts <= until)
    total = session.exec(select(func.count()).select_from(AuditLog).where(*filters)).one()
    items = session.exec(
        select(AuditLog).where(*filters).order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    # snapshot before recording, so the viewer's own row doesn't shift the page
    items = [i.model_dump() for i in items]
    record(
        session,
        request,
        "audit_view",
        user,
        detail={
            "filters": {
                "case_id": case_id,
                "user_id": user_id,
                "action": action,
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
            }
        },
    )
    return {"items": items, "total": total}


@router.get("/verify")
def verify(request: Request, user: User = Depends(require_role("admin")), session: Session = Depends(get_session)):
    result = verify_chain(session)
    record(session, request, "audit_view", user, detail={"verify": result["ok"]})
    return result
