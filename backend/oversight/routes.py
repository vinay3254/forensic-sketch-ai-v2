"""Admin oversight of investigators, built from the hash-chained audit log.

Each investigator (officer) can be assigned to one admin. An admin sees the investigators
assigned to them, investigators not yet assigned to anyone (so nobody goes unwatched), and
every admin. A session runs from a login to the matching logout; it ends early when the same
person logs in again without logging out, and counts as active until the token would expire."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.audit.logger import record
from backend.auth.deps import require_role
from backend.db import get_session
from backend.errors import AppError
from backend.models import AuditLog, Case, User

router = APIRouter(prefix="/api/admin", tags=["oversight"])
admin_only = require_role("admin")


def visible(admin: User, u: User) -> bool:
    return u.role == "admin" or u.supervisor_id in (None, admin.id)


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def sessions_of(rows: list[AuditLog], expiry: timedelta) -> list[dict]:
    """Rows of one user, oldest first -> sessions, oldest first. Rows before any login are skipped."""
    out: list[dict] = []
    cur: dict | None = None
    for r in rows:
        if r.action == "login":
            if cur and cur["end_reason"] is None:
                cur.update(end=r.ts, end_reason="new_login")
            cur = {"login": r, "rows": [r], "end": None, "end_reason": None}
            out.append(cur)
        elif cur and cur["end_reason"] is None:
            cur["rows"].append(r)
            if r.action == "logout":
                cur.update(end=r.ts, end_reason="logout")
    now = datetime.now(UTC)
    for s in out:
        if s["end_reason"] is None:
            expires = _aware(s["login"].ts) + expiry
            if expires > now:
                s["end_reason"] = "active"
            else:
                s.update(end=expires, end_reason="expired")
    return out


def _rows_by_user(session: Session) -> dict[int, list[AuditLog]]:
    by: dict[int, list[AuditLog]] = {}
    for r in session.exec(select(AuditLog).where(AuditLog.user_id.is_not(None)).order_by(AuditLog.id)).all():
        by.setdefault(r.user_id, []).append(r)
    return by


def _person(u: User, rows: list[AuditLog], sessions: list[dict], failed: int, names: dict[int, str]) -> dict:
    acts = Counter(r.action for r in rows)
    logins = [r.ts for r in rows if r.action == "login"]
    logouts = [r.ts for r in rows if r.action == "logout"]
    return {
        "user_id": u.id, "username": u.username, "role": u.role,
        "supervisor_id": u.supervisor_id, "supervisor": names.get(u.supervisor_id),
        "logins": acts["login"], "logouts": acts["logout"], "failed_logins": failed,
        "last_login": max(logins) if logins else None, "last_logout": max(logouts) if logouts else None,
        "last_seen": rows[-1].ts if rows else None,
        "active_now": bool(sessions) and sessions[-1]["end_reason"] == "active",
        "sessions": len(sessions), "actions": len(rows),
        "cases": len({r.case_id for r in rows if r.case_id is not None}),
        "cases_created": acts["case_create"], "sketches": acts["generate"] + acts["refine"],
        "denied": acts["access_denied"],
    }


def _target(session: Session, request: Request, admin: User, user_id: int) -> User:
    u = session.get(User, user_id)
    if u is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    if not visible(admin, u):
        record(session, request, "access_denied", admin, detail={"user_id": u.id, "reason": "assigned to another admin"})
        raise AppError("FORBIDDEN", "This investigator is overseen by another admin.", 403)
    return u


@router.get("/overview")
def overview(request: Request, admin: User = Depends(admin_only), session: Session = Depends(get_session)):
    expiry = timedelta(hours=request.app.state.settings.jwt_expiry_hours)
    users = session.exec(select(User).order_by(User.username)).all()
    names = {u.id: u.username for u in users}
    by_user = _rows_by_user(session)
    failed = Counter(
        r.username for r in session.exec(select(AuditLog).where(AuditLog.action == "login_failed")).all()
    )
    people = []
    for u in users:
        if not visible(admin, u):
            continue
        rows = by_user.get(u.id, [])
        people.append(_person(u, rows, sessions_of(rows, expiry), failed[u.username], names))
    team = [p for p in people if p["role"] != "admin"]
    admins = [p for p in people if p["role"] == "admin"]
    record(session, request, "oversight_view", admin, detail={"view": "overview"})
    return {
        "team": team,
        "admins": admins,
        "admin_choices": [{"id": u.id, "username": u.username} for u in users if u.role == "admin"],
        "totals": {
            "investigators": len(team),
            "mine": sum(p["supervisor_id"] == admin.id for p in team),
            "unassigned": sum(p["supervisor_id"] is None for p in team),
            "active_now": sum(p["active_now"] for p in people),
            "logins": sum(p["logins"] for p in people),
            "failed_logins": sum(p["failed_logins"] for p in people),
            "cases": len({r.case_id for p in people for r in by_user.get(p["user_id"], []) if r.case_id}),
        },
    }


class SupervisorIn(BaseModel):
    admin_id: int | None


@router.put("/users/{user_id}/supervisor")
def assign(
    user_id: int, body: SupervisorIn, request: Request,
    admin: User = Depends(admin_only), session: Session = Depends(get_session),
):
    u = _target(session, request, admin, user_id)
    if u.role == "admin":
        raise AppError("VALIDATION", "Only investigators are assigned to an admin.", 422)
    if body.admin_id is not None:
        sup = session.get(User, body.admin_id)
        if sup is None or sup.role != "admin":
            raise AppError("VALIDATION", "An investigator can only be assigned to an admin.", 422)
    before = u.supervisor_id
    u.supervisor_id = body.admin_id
    session.add(u)
    session.commit()
    record(session, request, "supervisor_assign", admin, detail={"user_id": u.id, "from": before, "to": body.admin_id})
    return {"user_id": u.id, "supervisor_id": u.supervisor_id}


def _case_refs(session: Session, ids: set[int]) -> dict[int, Case]:
    return {c.id: c for c in session.exec(select(Case).where(Case.id.in_(ids))).all()} if ids else {}


@router.get("/users/{user_id}/sessions")
def user_sessions(
    user_id: int, request: Request, admin: User = Depends(admin_only), session: Session = Depends(get_session),
):
    u = _target(session, request, admin, user_id)
    rows = session.exec(select(AuditLog).where(AuditLog.user_id == u.id).order_by(AuditLog.id)).all()
    sessions = sessions_of(rows, timedelta(hours=request.app.state.settings.jwt_expiry_hours))
    cases = _case_refs(session, {r.case_id for r in rows if r.case_id})
    out = []
    for s in reversed(sessions):
        ids = sorted({r.case_id for r in s["rows"] if r.case_id})
        out.append({
            "id": s["login"].id, "start": s["login"].ts, "end": s["end"], "end_reason": s["end_reason"],
            "ip": s["login"].ip, "user_agent": s["login"].user_agent, "actions": len(s["rows"]),
            "by_action": dict(Counter(r.action for r in s["rows"])),
            "cases": [{"id": i, "case_number": cases[i].case_number, "title": cases[i].title} for i in ids if i in cases],
        })
    record(session, request, "oversight_view", admin, detail={"view": "sessions", "user_id": u.id})
    return out


@router.get("/users/{user_id}/sessions/{login_id}")
def session_timeline(
    user_id: int, login_id: int, request: Request,
    admin: User = Depends(admin_only), session: Session = Depends(get_session),
):
    u = _target(session, request, admin, user_id)
    rows = session.exec(select(AuditLog).where(AuditLog.user_id == u.id).order_by(AuditLog.id)).all()
    sessions = sessions_of(rows, timedelta(hours=request.app.state.settings.jwt_expiry_hours))
    s = next((s for s in sessions if s["login"].id == login_id), None)
    if s is None:
        raise AppError("NOT_FOUND", "Session not found.", 404)
    record(session, request, "oversight_view", admin, detail={"view": "session", "user_id": u.id, "login_id": login_id})
    return [r.model_dump(exclude={"prev_hash", "hash"}) for r in s["rows"]]


@router.get("/users/{user_id}/cases")
def user_cases(
    user_id: int, request: Request, admin: User = Depends(admin_only), session: Session = Depends(get_session),
):
    u = _target(session, request, admin, user_id)
    rows = session.exec(
        select(AuditLog).where(AuditLog.user_id == u.id, AuditLog.case_id.is_not(None)).order_by(AuditLog.id)
    ).all()
    by_case: dict[int, list[AuditLog]] = {}
    for r in rows:
        by_case.setdefault(r.case_id, []).append(r)
    cases = _case_refs(session, set(by_case))
    out = [
        {
            "case_id": cid, "case_number": cases[cid].case_number if cid in cases else None,
            "title": cases[cid].title if cid in cases else "(deleted case)",
            "owned": cid in cases and cases[cid].created_by == u.id,
            "first": rs[0].ts, "last": rs[-1].ts, "actions": len(rs), "by_action": dict(Counter(r.action for r in rs)),
        }
        for cid, rs in by_case.items()
    ]
    out.sort(key=lambda c: c["last"], reverse=True)
    record(session, request, "oversight_view", admin, detail={"view": "cases", "user_id": u.id})
    return out
