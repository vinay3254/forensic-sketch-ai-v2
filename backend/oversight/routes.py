"""Admin oversight of investigators, built from the hash-chained audit log.

Each investigator (officer) can be assigned to one admin. An admin sees the investigators
assigned to them, investigators not yet assigned to anyone (so nobody goes unwatched), and
every admin. A session runs from a login to the matching logout; it ends early when the same
person logs in again without logging out, and counts as active until the token would expire."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.audit.logger import record
from backend.auth.deps import require_role
from backend.db import get_session
from backend.errors import AppError
from backend.live import ACTIVE_S, case_of, page_label
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


# what kind of work each audit action is, for the dashboard's charts
GROUPS = {
    "sketch": {"generate", "refine", "revert", "make_photo", "variant_create", "style_apply", "proportion_adjust",
               "translate", "body_create", "body_realistic", "body_reconstruct", "body_model_blender",
               "figure_update", "figure_save", "head_create", "angle_view_create"},
    "interview": {"interview_start", "interview_assist", "interview_confirm"},
    "casework": {"case_create", "case_update", "case_open", "case_list", "image_view", "export", "record_search",
                 "record_view"},
}
QUIET = {"oversight_view", "audit_view"}
VIEW_EVERY = timedelta(minutes=10)  # admins looking at logs is not investigator activity


def group_of(action: str) -> str:
    return next((g for g, acts in GROUPS.items() if action in acts), "account")


@router.get("/dashboard")
def dashboard(
    request: Request,
    days: int = Query(14, ge=1, le=90),
    admin: User = Depends(admin_only),
    session: Session = Depends(get_session),
):
    expiry = timedelta(hours=request.app.state.settings.jwt_expiry_hours)
    now = datetime.now(UTC)
    first_day = (now - timedelta(days=days - 1)).date()
    since = datetime.combine(first_day, datetime.min.time(), UTC)
    users = [u for u in session.exec(select(User).order_by(User.username)).all() if visible(admin, u)]
    names = {u.id: u.username for u in session.exec(select(User)).all()}
    by_user = _rows_by_user(session)
    day_keys = [(first_day + timedelta(days=i)).isoformat() for i in range(days)]
    daily = {d: {"date": d, "groups": {"sketch": 0, "interview": 0, "casework": 0, "account": 0}, "logins": 0,
                 "failed": 0} for d in day_keys}

    def day_of(ts: datetime) -> str:
        return _aware(ts).date().isoformat()

    failed_rows = session.exec(
        select(AuditLog).where(AuditLog.action == "login_failed", AuditLog.ts >= since)
    ).all()
    visible_names = {u.username for u in users}
    for r in failed_rows:
        if r.username in visible_names and day_of(r.ts) in daily:
            daily[day_of(r.ts)]["failed"] += 1
    failed_by = Counter(r.username for r in failed_rows if r.username in visible_names)

    presence = request.app.state.presence
    now_ts = now.timestamp()
    tasks = sorted(presence.tasks.values(), key=lambda t: t["started"])
    task_cases = _case_refs(session, {t["case_id"] for t in tasks if t["case_id"]})
    seen_pages = {uid: page for uid, (_, page) in presence.seen.items()}
    page_cases = _case_refs(session, {c for c in map(case_of, seen_pages.values()) if c})

    def task_out(t):
        c = task_cases.get(t["case_id"])
        return {"user_id": t["user_id"], "username": names.get(t["user_id"]), "label": t["label"],
                "case_id": t["case_id"], "case_number": c.case_number if c else None,
                "case_title": c.title if c else None, "started": datetime.fromtimestamp(t["started"], UTC)}

    def page_out(path):
        label, c = page_label(path), page_cases.get(case_of(path))
        return f"{label} · {c.case_number}" if label and c else label

    people, timeline, recent, case_ids = [], [], [], set()
    for u in users:
        rows = by_user.get(u.id, [])
        sessions = sessions_of(rows, expiry)
        # last active: the latest request (presence) or, after a restart, the latest logged action
        seen = presence.seen.get(u.id)
        last_active = datetime.fromtimestamp(seen[0], UTC) if seen else (_aware(rows[-1].ts) if rows else None)
        if not sessions:
            status = "never"
        elif sessions[-1]["end_reason"] != "active":
            status = "signed_out"
        else:
            status = "active" if last_active and now_ts - last_active.timestamp() <= ACTIVE_S else "idle"
        in_range = [r for r in rows if _aware(r.ts) >= since and r.action not in QUIET]
        per_day = Counter(day_of(r.ts) for r in in_range)
        for r in in_range:
            daily[day_of(r.ts)]["groups"][group_of(r.action)] += 1
            if r.action == "login":
                daily[day_of(r.ts)]["logins"] += 1
        cases = {r.case_id for r in in_range if r.case_id}
        case_ids |= cases
        recent += in_range
        mine = [s for s in sessions if (s["end"] is None or _aware(s["end"]) >= since)]
        for s in mine:
            open_now = s["end_reason"] == "active"
            timeline.append({
                "user_id": u.id, "username": u.username, "start": s["login"].ts,
                # an open session runs to now while the person is active, to their last activity when idle
                "end": None if open_now and status == "active" else (last_active if open_now else s["end"]),
                "end_reason": (status if open_now else s["end_reason"]),
                "actions": len(s["rows"]), "cases": len({r.case_id for r in s["rows"] if r.case_id}),
            })
        acts = Counter(r.action for r in in_range)
        people.append({
            "user_id": u.id, "username": u.username, "role": u.role, "supervisor": names.get(u.supervisor_id),
            "status": status, "online": status == "active",
            "last_seen": last_active,
            "page": page_out(seen_pages.get(u.id)) if status in ("active", "idle") else None,
            "doing": [task_out(t) for t in tasks if t["user_id"] == u.id], "sessions": len(mine), "cases": len(cases),
            "actions": len(in_range), "sketches": acts["generate"] + acts["refine"],
            "failed_logins": failed_by[u.username], "denied": acts["access_denied"],
            "daily_actions": [per_day[d] for d in day_keys],
        })
    refs = _case_refs(session, {r.case_id for r in recent if r.case_id})
    recent.sort(key=lambda r: r.id, reverse=True)
    # the dashboard refreshes itself live; log the admin viewing it once per 10 minutes, not every refresh
    last_view = session.exec(
        select(AuditLog).where(AuditLog.user_id == admin.id, AuditLog.action == "oversight_view")
        .order_by(AuditLog.id.desc())
    ).first()
    if not (last_view and last_view.detail.get("view") == "dashboard" and now - _aware(last_view.ts) < VIEW_EVERY):
        record(session, request, "oversight_view", admin, detail={"view": "dashboard", "days": days})
    return {
        "days": days,
        "daily": list(daily.values()),
        "people": people,
        "in_progress": [task_out(t) for t in tasks if t["user_id"] in {u.id for u in users}],
        "now": now,
        "sessions": sorted(timeline, key=lambda s: s["start"]),
        "recent": [
            {"id": r.id, "ts": r.ts, "username": r.username, "action": r.action, "group": group_of(r.action),
             "case_id": r.case_id, "case_number": refs[r.case_id].case_number if r.case_id in refs else None,
             "case_title": refs[r.case_id].title if r.case_id in refs else None}
            for r in recent[:20]
        ],
        "totals": {
            "investigators": sum(p["role"] != "admin" for p in people),
            "admins": sum(p["role"] == "admin" for p in people),
            "online": sum(p["status"] == "active" for p in people),
            "idle": sum(p["status"] == "idle" for p in people),
            "sessions": len(timeline),
            "cases": len(case_ids),
            "sketches": sum(p["sketches"] for p in people),
            "failed_logins": sum(failed_by.values()),
            "denied": sum(p["denied"] for p in people),
        },
    }
