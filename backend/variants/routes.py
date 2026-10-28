from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from backend.ai.client import AIClient, get_ai_client
from backend.ai.prompts import VARIANTS
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.db import get_session
from backend.errors import AppError
from backend.face.routes import version_of_case
from backend.face.service import existing_image_file
from backend.models import Case, FaceVersion, User, Variant
from backend.variants.service import create_variant

router = APIRouter(prefix="/api/cases/{case_id}", tags=["variants"])


class VariantIn(BaseModel):
    kind: str

    @field_validator("kind")
    @classmethod
    def known_kind(cls, kind: str) -> str:
        if kind not in VARIANTS:
            raise ValueError(f"unknown variant '{kind}'")
        return kind


class VariantOut(BaseModel):
    id: int
    version_id: int
    version_no: int
    kind: str
    label: str
    localized: bool
    image_url: str
    created_at: datetime

    @classmethod
    def of(cls, x: Variant, version_no: int) -> "VariantOut":
        return cls(
            id=x.id, version_id=x.version_id, version_no=version_no, kind=x.kind, label=VARIANTS[x.kind][0],
            localized=x.localized, image_url=f"/api/cases/{x.case_id}/variants/{x.id}/image", created_at=x.created_at,
        )


@router.post("/versions/{version_id}/variants", response_model=VariantOut)
def make_variant(
    version_id: int,
    body: VariantIn,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    v = version_of_case(session, case, version_id)
    state = request.app.state
    try:
        x = create_variant(session, ai, state.settings, state.face_parser, case, user, v, body.kind)
    except AppError as e:
        record(session, request, "variant_create", user, case_id=case.id, version_id=v.id,
               detail={"kind": body.kind, "outcome": e.code})
        raise
    record(session, request, "variant_create", user, case_id=case.id, version_id=v.id,
           detail={"kind": body.kind, "outcome": "ok", "variant_id": x.id, "localized": x.localized})
    return VariantOut.of(x, v.version_no)


@router.get("/variants", response_model=list[VariantOut])
def list_variants(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    rows = session.exec(
        select(Variant, FaceVersion.version_no)
        .join(FaceVersion, Variant.version_id == FaceVersion.id)
        .where(Variant.case_id == case.id)
        .order_by(Variant.id.desc())
    ).all()
    return [VariantOut.of(x, no) for x, no in rows]


@router.get("/variants/{variant_id}/image")
def variant_image(
    variant_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    x = session.get(Variant, variant_id)
    if x is None or x.case_id != case.id:
        raise AppError("NOT_FOUND", "Variant not found.", 404)
    path = existing_image_file(request.app.state.settings, x.image_path)
    record(session, request, "image_view", user, case_id=case.id, version_id=x.version_id, detail={"variant_id": x.id})
    return FileResponse(path, media_type="image/png")
