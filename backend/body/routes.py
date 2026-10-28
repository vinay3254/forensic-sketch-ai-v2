import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.ai.client import AIClient, get_ai_client
from backend.ai.prompts import build_body_prompt
from backend.ai.schemas import Attributes
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.cases.details import CaseDetails
from backend.db import get_session
from backend.errors import AppError
from backend.face.service import existing_image_file, image_file, latest_version, normalize_image
from backend.models import BodyFigure, Case, User

router = APIRouter(prefix="/api/cases/{case_id}", tags=["body"])


class BodyOut(BaseModel):
    id: int
    image_url: str
    created_at: datetime

    @classmethod
    def of(cls, b: BodyFigure) -> "BodyOut":
        return cls(id=b.id, image_url=f"/api/cases/{b.case_id}/body/{b.id}/image", created_at=b.created_at)


def latest_body(session: Session, case_id: int) -> BodyFigure | None:
    return session.exec(select(BodyFigure).where(BodyFigure.case_id == case_id).order_by(BodyFigure.id.desc())).first()


@router.post("/body", response_model=BodyOut)
def draw_body(
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    settings = request.app.state.settings
    version = latest_version(session, case.id)
    attrs = Attributes(**version.attributes) if version else Attributes()
    details = CaseDetails(**(case.details or {}))
    try:
        if version:  # draw from the sketch itself so the figure has the same face
            prompt = build_body_prompt(attrs, details, from_sketch=True)
            raw = ai.edit_image(existing_image_file(settings, version.image_path).read_bytes(), prompt)
        else:
            prompt = build_body_prompt(attrs, details)
            raw = ai.generate_image(prompt)
        image = normalize_image(raw, settings.llm_image_size)
    except AppError as e:
        record(session, request, "body_create", user, case_id=case.id, detail={"outcome": e.code})
        raise
    rel = f"cases/{case.id}/body-{uuid.uuid4().hex[:8]}.png"
    path = image_file(settings, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image)
    body = BodyFigure(case_id=case.id, image_path=rel, prompt=prompt, created_by=user.id)
    session.add(body)
    session.commit()
    session.refresh(body)
    record(session, request, "body_create", user, case_id=case.id, detail={"outcome": "ok", "body_id": body.id})
    return BodyOut.of(body)


@router.get("/body", response_model=BodyOut)
def get_body(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    body = latest_body(session, case.id)
    if body is None:
        raise AppError("NOT_FOUND", "No full-body figure yet.", 404)
    return BodyOut.of(body)


@router.get("/body/{body_id}/image")
def body_image(
    body_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    body = session.get(BodyFigure, body_id)
    if body is None or body.case_id != case.id:
        raise AppError("NOT_FOUND", "Figure not found.", 404)
    path = existing_image_file(request.app.state.settings, body.image_path)
    record(session, request, "image_view", user, case_id=case.id, detail={"body_id": body.id})
    return FileResponse(path, media_type="image/png")
