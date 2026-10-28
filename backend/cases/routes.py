from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.db import get_session
from backend.errors import AppError
from backend.models import Case, ChatMessage, FaceVersion, User

router = APIRouter(prefix="/api/cases", tags=["cases"])

CASE_NUMBER_ATTEMPTS = 3


class CaseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class CaseOut(BaseModel):
    id: int
    case_number: str
    title: str
    status: str
    created_at: datetime
    created_by: int


class VersionOut(BaseModel):
    id: int
    version_no: int
    kind: str
    instruction: str
    attributes: dict
    created_at: datetime
    image_url: str
    photo_url: str | None
    interview_id: int | None
    uncertain: list[str]
    localized: bool

    @classmethod
    def of(cls, v: FaceVersion) -> "VersionOut":
        return cls(
            id=v.id,
            version_no=v.version_no,
            kind=v.kind,
            instruction=v.instruction,
            attributes=v.attributes,
            created_at=v.created_at,
            image_url=f"/api/cases/{v.case_id}/versions/{v.id}/image",
            photo_url=f"/api/cases/{v.case_id}/versions/{v.id}/photo" if v.photo_path else None,
            interview_id=v.interview_id,
            uncertain=v.uncertain or [],
            localized=bool(v.localized),
        )


class ChatOut(BaseModel):
    id: int
    role: str
    content: str
    version_id: int | None
    created_at: datetime


def next_case_number(session: Session) -> str:
    prefix = f"BLR-{datetime.now(UTC).year}-"
    last = session.exec(
        select(Case.case_number).where(Case.case_number.startswith(prefix)).order_by(Case.case_number.desc())
    ).first()
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


@router.post("", response_model=CaseOut)
def create_case(
    body: CaseIn, request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    for _ in range(CASE_NUMBER_ATTEMPTS):
        case = Case(case_number=next_case_number(session), title=body.title, created_by=user.id)
        session.add(case)
        try:
            session.commit()
            break
        except IntegrityError:  # another request took this number first
            session.rollback()
    else:
        raise AppError("CONFLICT", "Could not allocate a case number. Try again.", 409)
    session.refresh(case)
    record(session, request, "case_create", user, case_id=case.id)
    return CaseOut(**case.model_dump())


@router.get("", response_model=list[CaseOut])
def list_cases(request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    q = select(Case).order_by(Case.id.desc())
    if user.role != "admin":
        q = q.where(Case.created_by == user.id)
    cases = [CaseOut(**c.model_dump()) for c in session.exec(q).all()]
    record(session, request, "case_list", user)
    return cases


@router.get("/{case_id}")
def get_case(
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    versions = session.exec(
        select(FaceVersion).where(FaceVersion.case_id == case.id).order_by(FaceVersion.version_no)
    ).all()
    chat = session.exec(select(ChatMessage).where(ChatMessage.case_id == case.id).order_by(ChatMessage.id)).all()
    out = {
        "case": CaseOut(**case.model_dump()),
        "versions": [VersionOut.of(v) for v in versions],
        "chat": [ChatOut(**m.model_dump()) for m in chat],
    }
    record(session, request, "case_open", user, case_id=case.id)
    return out
