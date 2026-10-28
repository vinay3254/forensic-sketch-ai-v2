"""Search and read the demo criminal-records database. Every search and every record opened
is written to the audit log, like case access."""

from collections import Counter

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlmodel import Session, or_, select

from backend.audit.logger import record
from backend.auth.deps import current_user
from backend.db import get_session
from backend.errors import AppError
from backend.models import RecordCharge, RecordPerson, User

router = APIRouter(prefix="/api/records", tags=["records"])

NOTICE = (
    "Every person here is fictional. Faces are synthetic (FLUXSynID, CC BY-NC 4.0) and the cases are "
    "generated. An arrest or charge is not a conviction."
)
PENDING = {"under_investigation", "charge_sheeted"}


def _counts(charges: list[RecordCharge]) -> dict:
    c = Counter(x.status for x in charges)
    return {"cases": len(charges), "convicted": c["convicted"], "acquitted": c["acquitted"],
            "pending": sum(c[s] for s in PENDING)}


def _summary(p: RecordPerson, charges: list[RecordCharge]) -> dict:
    latest = max(charges, key=lambda c: c.date) if charges else None
    return {
        "id": p.id, "record_no": p.record_no, "name": p.name, "alias": p.alias, "gender": p.gender, "age": p.age,
        "area": p.area, "marks": p.marks, "photo_url": f"/api/records/{p.id}/photo",
        "latest_offence": latest.offence if latest else None, "latest_date": latest.date if latest else None,
        **_counts(charges),
    }


@router.get("")
def search(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    area: str | None = None,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    people = select(RecordPerson)
    if q and q.strip():
        like = f"%{q.strip()}%"
        offence_hits = select(RecordCharge.person_id).where(
            or_(RecordCharge.offence.ilike(like), RecordCharge.section.ilike(like), RecordCharge.fir_no.ilike(like))
        )
        people = people.where(or_(
            RecordPerson.name.ilike(like), RecordPerson.alias.ilike(like), RecordPerson.record_no.ilike(like),
            RecordPerson.marks.ilike(like), RecordPerson.area.ilike(like), RecordPerson.id.in_(offence_hits),
        ))
    if status:
        people = people.where(RecordPerson.id.in_(select(RecordCharge.person_id).where(RecordCharge.status == status)))
    if area:
        people = people.where(RecordPerson.id.in_(
            select(RecordCharge.person_id).where(RecordCharge.police_station == f"{area} Police Station")
        ))
    found = session.exec(people.order_by(RecordPerson.name)).all()
    charges = session.exec(select(RecordCharge)).all()
    by_person: dict[int, list[RecordCharge]] = {}
    for c in charges:
        by_person.setdefault(c.person_id, []).append(c)
    items = [_summary(p, by_person.get(p.id, [])) for p in found]
    # the most recent offenders first
    items.sort(key=lambda i: i["latest_date"] or "", reverse=True)
    record(session, request, "record_search", user,
           detail={"q": q or None, "status": status, "area": area, "results": len(items)})
    total_people = session.exec(select(RecordPerson.id)).all()
    return {
        "demo": True, "notice": NOTICE, "total": len(items), "items": items,
        "summary": {"people": len(total_people), **_counts(charges)},
        "areas": sorted({c.police_station.removesuffix(" Police Station") for c in charges}),
    }


def _person(session: Session, person_id: int) -> RecordPerson:
    p = session.get(RecordPerson, person_id)
    if p is None:
        raise AppError("NOT_FOUND", "Record not found.", 404)
    return p


@router.get("/{person_id}")
def read(person_id: int, request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    p = _person(session, person_id)
    charges = session.exec(select(RecordCharge).where(RecordCharge.person_id == p.id)).all()
    charges = sorted(charges, key=lambda c: c.date, reverse=True)
    record(session, request, "record_view", user, detail={"person_id": p.id, "record_no": p.record_no})
    return {
        **_summary(p, charges), "demo": True, "notice": NOTICE, "height_cm": p.height_cm, "build": p.build,
        "source": p.source,
        "charges": [c.model_dump(exclude={"person_id"}) for c in charges],
    }


@router.get("/{person_id}/photo")
def photo(person_id: int, request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    p = _person(session, person_id)
    path = request.app.state.settings.storage_dir / p.photo_path
    if not path.is_file():
        raise AppError("NOT_FOUND", "The photo for this record is missing.", 404)
    return FileResponse(path, media_type="image/jpeg")
