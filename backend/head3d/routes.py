import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.ai.client import AIClient, get_ai_client
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.db import get_session
from backend.errors import AppError
from backend.face import service
from backend.face.routes import version_of_case
from backend.models import Case, FaceVersion, Head3D, User

router = APIRouter(prefix="/api/cases/{case_id}", tags=["head3d"])


class HeadOut(BaseModel):
    id: int
    version_id: int
    version_no: int
    mesh_url: str
    created_at: datetime

    @classmethod
    def of(cls, h: Head3D, version_no: int) -> "HeadOut":
        return cls(
            id=h.id, version_id=h.version_id, version_no=version_no,
            mesh_url=f"/api/cases/{h.case_id}/heads/{h.id}/mesh", created_at=h.created_at,
        )


def head_of_case(session: Session, case: Case, head_id: int) -> Head3D:
    h = session.get(Head3D, head_id)
    if h is None or h.case_id != case.id:
        raise AppError("NOT_FOUND", "3D head not found.", 404)
    return h


@router.post("/versions/{version_id}/head", response_model=HeadOut)
def make_head(
    version_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    """TripoSR reads photos far better than pencil sketches, so the realistic photo is made first."""
    v = version_of_case(session, case, version_id)
    head3d, settings = request.app.state.head3d_client, request.app.state.settings
    if head3d is None:
        raise AppError("HEAD3D_OFF", "The 3D head service is not set up (HEAD3D_URL).", 503)
    try:
        had_photo = bool(v.photo_path)
        v = service.make_photo(session, ai, settings, v)
        if not had_photo:
            record(session, request, "make_photo", user, case_id=case.id, version_id=v.id, detail={"outcome": "ok"})
        mesh = head3d.make_head(service.existing_image_file(settings, v.photo_path).read_bytes())
    except AppError as e:
        record(session, request, "head_create", user, case_id=case.id, version_id=v.id, detail={"outcome": e.code})
        raise
    rel = f"cases/{case.id}/head-{uuid.uuid4().hex[:8]}.glb"
    path = service.image_file(settings, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(mesh)
    h = Head3D(case_id=case.id, version_id=v.id, mesh_path=rel, created_by=user.id)
    session.add(h)
    session.commit()
    session.refresh(h)
    record(session, request, "head_create", user, case_id=case.id, version_id=v.id, detail={"outcome": "ok", "head_id": h.id})
    return HeadOut.of(h, v.version_no)


@router.get("/heads", response_model=list[HeadOut])
def list_heads(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    rows = session.exec(
        select(Head3D, FaceVersion.version_no)
        .join(FaceVersion, Head3D.version_id == FaceVersion.id)
        .where(Head3D.case_id == case.id)
        .order_by(Head3D.id.desc())
    ).all()
    return [HeadOut.of(h, no) for h, no in rows]


@router.get("/heads/{head_id}/mesh")
def head_mesh(
    head_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    session: Session = Depends(get_session),
):
    h = head_of_case(session, case, head_id)
    return FileResponse(service.existing_image_file(request.app.state.settings, h.mesh_path), media_type="model/gltf-binary")
