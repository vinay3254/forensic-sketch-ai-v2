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
    action: str,
    case_id: int | None,
    version_id: int | None,
    detail: dict,
) -> str:
    payload = "|".join(
        [
            prev_hash,
            _canonical_ts(ts),
            str(user_id),
            action,
            str(case_id),
            str(version_id),
            json.dumps(detail, sort_keys=True),
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


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
        ts = utcnow()
        user_id = user.id if user else None
        row = AuditLog(
            ts=ts,
            user_id=user_id,
            username=user.username if user else username,
            role=user.role if user else None,
            action=action,
            case_id=case_id,
            version_id=version_id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail=detail,
            prev_hash=prev_hash,
            hash=compute_hash(prev_hash, ts, user_id, action, case_id, version_id, detail),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def verify_chain(session: Session) -> dict:
    rows = session.exec(select(AuditLog).order_by(AuditLog.id)).all()
    prev_hash = GENESIS_HASH
    for row in rows:
        expected = compute_hash(prev_hash, row.ts, row.user_id, row.action, row.case_id, row.version_id, row.detail)
        if row.prev_hash != prev_hash or row.hash != expected:
            return {"ok": False, "rows": len(rows), "first_bad_id": row.id}
        prev_hash = row.hash
    return {"ok": True, "rows": len(rows)}
