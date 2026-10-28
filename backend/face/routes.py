from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.ai.client import AIClient, get_ai_client
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.cases.routes import VersionOut
from backend.db import get_session
from backend.errors import AppError
from backend.face import service
from backend.models import Case, FaceVersion, User

router = APIRouter(prefix="/api/cases/{case_id}", tags=["face"])

MAX_TEXT = 2000


class GenerateIn(BaseModel):
    description: str = Field(min_length=1, max_length=MAX_TEXT)


class RefineIn(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_TEXT)


def version_of_case(session: Session, case: Case, version_id: int) -> FaceVersion:
    v = session.get(FaceVersion, version_id)
    if v is None or v.case_id != case.id:
        raise AppError("NOT_FOUND", "Version not found.", 404)
    return v


@router.post("/generate", response_model=VersionOut)
def generate(
    body: GenerateIn,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    try:
        v = service.generate_face(session, ai, request.app.state.settings, case, user, body.description)
    except AppError as e:
        record(session, request, "generate", user, case_id=case.id, detail={"outcome": e.code})
        raise
    record(session, request, "generate", user, case_id=case.id, version_id=v.id, detail={"outcome": "ok"})
    return VersionOut.of(v)


@router.post("/refine")
def refine(
    body: RefineIn,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    try:
        v, reply = service.refine_face(session, ai, request.app.state.settings, case, user, body.message)
    except AppError as e:
        record(session, request, "refine", user, case_id=case.id, detail={"message": body.message, "outcome": e.code})
        raise
    outcome = "ok" if v else "needs_clarification"
    record(
        session, request, "refine", user, case_id=case.id, version_id=v.id if v else None,
        detail={"message": body.message, "outcome": outcome},
    )
    return {"version": VersionOut.of(v) if v else None, "reply": reply}


@router.get("/versions", response_model=list[VersionOut])
def versions(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    rows = session.exec(
        select(FaceVersion).where(FaceVersion.case_id == case.id).order_by(FaceVersion.version_no)
    ).all()
    return [VersionOut.of(v) for v in rows]


@router.post("/versions/{version_id}/revert", response_model=VersionOut)
def revert(
    version_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    v = service.revert_face(session, request.app.state.settings, case, user, version_id)
    record(session, request, "revert", user, case_id=case.id, version_id=v.id)
    return VersionOut.of(v)


@router.get("/versions/{version_id}/image")
def image(
    version_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    v = version_of_case(session, case, version_id)
    record(session, request, "image_view", user, case_id=case.id, version_id=v.id)
    return FileResponse(service.image_file(request.app.state.settings, v.image_path), media_type="image/png")
