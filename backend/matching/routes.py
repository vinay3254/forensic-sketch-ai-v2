"""Suspect matching: compare a case's face with the records' mugshots and list the closest as leads.

The query is the version's realistic photo when one has been made (photo against photo is far more
reliable), otherwise the sketch. Each record's fingerprint is computed once and kept on the record.
Every search is audited with the people and scores it returned. A match is a lead to check, never an
identification."""

import numpy as np
from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.db import get_session
from backend.errors import AppError
from backend.face.routes import version_of_case
from backend.face.service import existing_image_file
from backend.matching.faces import NoFace
from backend.models import Case, RecordCharge, RecordPerson, User
from backend.records.routes import _summary

router = APIRouter(prefix="/api/cases/{case_id}", tags=["matching"])

STRONG, POSSIBLE = 0.50, 0.35  # cosine similarity; same person ~0.6-0.9, different people mostly under 0.3
TOP = 5
NOTICE = (
    "These are leads, not identifications: the closest faces in the records database. A high score means the "
    "faces look alike, not that this is the person. Check every lead against the facts of the case."
)


def band(score: float) -> str:
    return "strong" if score >= STRONG else "possible" if score >= POSSIBLE else "weak"


def record_vectors(session: Session, settings, matcher) -> tuple[list[RecordPerson], np.ndarray]:
    people = session.exec(select(RecordPerson).order_by(RecordPerson.id)).all()
    changed = False
    for p in people:
        if p.face_vector is None:
            path = settings.storage_dir / p.photo_path
            try:
                p.face_vector = matcher.embed(path.read_bytes()).round(5).tolist() if path.is_file() else []
            except NoFace:
                p.face_vector = []  # no usable face in the mugshot: never matched
            session.add(p)
            changed = True
    if changed:
        session.commit()
    usable = [p for p in people if p.face_vector]
    return usable, np.array([p.face_vector for p in usable], np.float32).reshape(len(usable), -1)


@router.post("/versions/{version_id}/matches")
def matches(
    version_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    v = version_of_case(session, case, version_id)
    state = request.app.state
    matcher = state.face_matcher
    if matcher is None:
        raise AppError("MATCHING_OFF", "Suspect matching needs the face models: run scripts.fetch_face_matcher, then restart.", 503)
    query = "photo" if v.photo_path else "sketch"
    image = existing_image_file(state.settings, v.photo_path or v.image_path).read_bytes()
    try:
        q = matcher.embed(image)
    except NoFace:
        raise AppError("NO_FACE", f"No face could be found in this {query}.", 422)
    people, vectors = record_vectors(session, state.settings, matcher)
    if not people:
        raise AppError("NOT_FOUND", "The records database is empty: run scripts.seed_records.", 404)
    scores = vectors @ q
    order = np.argsort(-scores)[:TOP]
    charges = session.exec(select(RecordCharge).where(RecordCharge.person_id.in_([people[i].id for i in order]))).all()
    results = []
    for i in order:
        p = people[i]
        s = float(scores[i])
        results.append({**_summary(p, [c for c in charges if c.person_id == p.id]), "score": round(s, 3), "band": band(s)})
    record(session, request, "suspect_match", user, case_id=case.id, version_id=v.id,
           detail={"query": query, "top": [{"person_id": r["id"], "score": r["score"]} for r in results]})
    return {"query": query, "notice": NOTICE, "thresholds": {"strong": STRONG, "possible": POSSIBLE},
            "searched": len(people), "results": results}
