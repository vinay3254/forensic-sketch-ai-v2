"""Full-body image reconstruction, stored separately from mannequin settings."""

from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.body.routes import latest_body
from backend.db import get_session
from backend.errors import AppError
from backend.face.service import existing_image_file, image_file
from backend.figure.routes import current_params, worker_of
from backend.figure.glb import validate_glb
from backend.models import BodyFigure, BodyModel, Case, User

router = APIRouter(prefix="/api/cases/{case_id}/figure", tags=["body reconstruction"])


class ReconstructIn(BaseModel):
    body_id: int | None = Field(default=None, gt=0)


class BodyModelOut(BaseModel):
    id: int
    body_id: int
    mesh_url: str
    source_url: str
    height_cm: float
    engine: str
    created_at: datetime
    blend_url: str | None = None
    script_url: str | None = None
    summary: str | None = None

    @classmethod
    def of(cls, m: BodyModel):
        return cls(id=m.id, body_id=m.body_id, height_cm=m.height_cm, engine=m.engine,
                   mesh_url=f"/api/cases/{m.case_id}/figure/reconstructions/{m.id}/model.glb",
                   source_url=f"/api/cases/{m.case_id}/body/{m.body_id}/image", created_at=m.created_at,
                   blend_url=f"/api/cases/{m.case_id}/figure/reconstructions/{m.id}/model.blend" if m.blend_path else None,
                   script_url=f"/api/cases/{m.case_id}/figure/reconstructions/{m.id}/script.py" if m.script_path else None,
                   summary=m.summary)


def model_of(session, case, model_id):
    model = session.get(BodyModel, model_id)
    if model is None or model.case_id != case.id:
        raise AppError("NOT_FOUND", "Reconstructed model not found.", 404)
    return model


@router.get("/reconstruction", response_model=BodyModelOut | None)
def latest(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    model = session.exec(select(BodyModel).where(BodyModel.case_id == case.id).order_by(BodyModel.id.desc())).first()
    return BodyModelOut.of(model) if model else None


@router.post("/reconstruct", response_model=BodyModelOut)
def reconstruct(body: ReconstructIn, request: Request, case: Case = Depends(require_case_access),
                user: User = Depends(current_user), session: Session = Depends(get_session)):
    source = session.get(BodyFigure, body.body_id) if body.body_id else latest_body(session, case.id)
    if source is None or source.case_id != case.id:
        raise AppError("NOT_FOUND", "Draw a full-body image first.", 404)
    worker = request.app.state.head3d_client
    if worker is None:
        raise AppError("BODY3D_OFF", "Local image-to-3D service is not running. Start the reconstruction worker.", 503)
    settings = request.app.state.settings
    height = current_params(session, case).height_cm
    try:
        mesh = worker.make_body(existing_image_file(settings, source.image_path).read_bytes(), height)
        try:
            validate_glb(mesh)
        except ValueError:
            raise AppError("INVALID_MODEL", "Reconstruction service returned an invalid 3D model.", 502)
    except AppError as error:
        record(session, request, "body_reconstruct", user, case_id=case.id, detail={"body_id": source.id, "outcome": error.code})
        raise
    rel = f"cases/{case.id}/body-model-{uuid.uuid4().hex}.glb"
    path = image_file(settings, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(mesh)
    model = BodyModel(case_id=case.id, body_id=source.id, mesh_path=rel, height_cm=height,
                      engine="TripoSR + reference projection", created_by=user.id)
    session.add(model)
    session.commit()
    session.refresh(model)
    record(session, request, "body_reconstruct", user, case_id=case.id, detail={"body_id": source.id, "model_id": model.id, "outcome": "ok"})
    return BodyModelOut.of(model)


@router.get("/reconstructions/{model_id}/model.glb")
def mesh(model_id: int, request: Request, case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    model = model_of(session, case, model_id)
    return FileResponse(existing_image_file(request.app.state.settings, model.mesh_path), media_type="model/gltf-binary")


@router.post("/reconstructions/{model_id}/blender")
def open_blender(model_id: int, request: Request, case: Case = Depends(require_case_access),
                 user: User = Depends(current_user), session: Session = Depends(get_session)):
    model = model_of(session, case, model_id)
    worker_of(request).import_glb(existing_image_file(request.app.state.settings, model.mesh_path).read_bytes())
    record(session, request, "body_model_blender", user, case_id=case.id, detail={"model_id": model.id})
    return {"opened": True}


@router.get('/reconstructions/{model_id}/model.blend')
def blend_file(model_id: int, request: Request, case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    model = model_of(session, case, model_id)
    if not model.blend_path:
        raise AppError('NOT_FOUND', 'This model has no Blender project file.', 404)
    return FileResponse(existing_image_file(request.app.state.settings, model.blend_path),
                        media_type='application/x-blender', filename=f'figure-{model.id}.blend')


@router.get('/reconstructions/{model_id}/script.py')
def script_file(model_id: int, request: Request, case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    model = model_of(session, case, model_id)
    if not model.script_path:
        raise AppError('NOT_FOUND', 'This model has no generated script.', 404)
    return FileResponse(existing_image_file(request.app.state.settings, model.script_path),
                        media_type='text/plain', filename=f'figure-{model.id}.py')
