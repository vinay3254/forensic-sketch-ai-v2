import hashlib
import json
import threading
from datetime import UTC, datetime

from fastapi import Request
from sqlmodel import Session, select

from backend.models import AuditLog, User, utcnow

GENESIS_HASH = "0" * 64
_chain_lock = threading.Lock()  # one writer at a time keeps prev_hash -> hash consistent


def _canonical_ts(ts: datetime) -> str:
    # SQLite returns naive datetimes; normalise both sides to naive UTC
    if ts.tzinfo is not None:
        ts = ts.astimezone(UTC).replace(tzinfo=None)
    return ts.isoformat()


def compute_hash(
    prev_hash: str,
    ts: datetime,
    user_id: int | None,
    username: str | None,
    role: str | None,
    action: str,
    case_id: int | None,
    version_id: int | None,
    ip: str | None,
    user_agent: str | None,
    detail: dict,
) -> str:
    # JSON array, not a joined string, so a "|" inside a user agent cannot shift fields
    payload = json.dumps(
        [prev_hash, _canonical_ts(ts), user_id, username, role, action, case_id, version_id, ip, user_agent, detail],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _row_hash(prev_hash: str, row: AuditLog) -> str:
    return compute_hash(
        prev_hash, row.ts, row.user_id, row.username, row.role, row.action,
        row.case_id, row.version_id, row.ip, row.user_agent, row.detail,
    )


def record(
    session: Session,
    request: Request,
    action: str,
    user: User | None = None,
    *,
    username: str | None = None,
    case_id: int | None = None,
    version_id: int | None = None,
    detail: dict | None = None,
) -> AuditLog:
    detail = detail or {}
    with _chain_lock:
        last = session.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
        prev_hash = last.hash if last else GENESIS_HASH
        row = AuditLog(
            ts=utcnow(),
            user_id=user.id if user else None,
            username=user.username if user else username,
            role=user.role if user else None,
            action=action,
            case_id=case_id,
            version_id=version_id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail=detail,
            prev_hash=prev_hash,
            hash="",
        )
        row.hash = _row_hash(prev_hash, row)
        session.add(row)
        session.commit()
        session.refresh(row)
    changes = getattr(request.app.state, "changes", None)
    # the live dashboard refreshes on every new row, except admins looking at logs: those rows would
    # make every open dashboard refresh, log another view, and so on for ever
    if changes is not None and action not in ("oversight_view", "audit_view"):
        changes.bump()
    return row


def verify_chain(session: Session) -> dict:
    """Check every link. Deleting rows from the end leaves a valid chain, so the head is
    returned too: an auditor who noted an earlier head can confirm it is still in the log."""
    rows = session.exec(select(AuditLog).order_by(AuditLog.id)).all()
    prev_hash = GENESIS_HASH
    for row in rows:
        if row.prev_hash != prev_hash or row.hash != _row_hash(prev_hash, row):
            return {"ok": False, "rows": len(rows), "first_bad_id": row.id}
        prev_hash = row.hash
    head = rows[-1] if rows else None
    return {"ok": True, "rows": len(rows), "head_id": head.id if head else None, "head_hash": prev_hash}
