import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from backend.ai.client import AIClient, get_ai_client
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.db import get_session
from backend.errors import AppError
from backend.face.service import image_file, latest_version
from backend.figure.params import FigureParams, apply_changes, defaults_for
from backend.models import BodyFigure, Case, User

router = APIRouter(prefix="/api/cases/{case_id}", tags=["figure"])


class FigureOut(BaseModel):
    params: FigureParams
    model_url: str
    reply: str | None = None


class PromptIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


def current_params(session: Session, case: Case) -> FigureParams:
    if case.figure:
        return FigureParams(**case.figure)
    v = latest_version(session, case.id)
    return defaults_for(case.details or {}, v.attributes if v else {})


def worker_of(request: Request):
    w = request.app.state.figure_worker
    if w is None:
        raise AppError("FIGURE_OFF", "The Blender figure worker is not set up (FIGURE_URL).", 503)
    return w


def out(case: Case, p: FigureParams, reply: str | None = None) -> FigureOut:
    return FigureOut(params=p, model_url=f"/api/cases/{case.id}/figure/model.glb", reply=reply)


def _store(session: Session, request: Request, user: User, case: Case, p: FigureParams, detail: dict) -> None:
    case.figure = p.model_dump()
    session.add(case)
    session.commit()
    record(session, request, "figure_update", user, case_id=case.id, detail=detail)


@router.get("/figure", response_model=FigureOut)
def get_figure(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    return out(case, current_params(session, case))


@router.put("/figure", response_model=FigureOut)
def put_figure(
    body: FigureParams,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    _store(session, request, user, case, body, {"source": "sliders"})
    return out(case, body)


@router.post("/figure/prompt", response_model=FigureOut)
def prompt_figure(
    body: PromptIn,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    """The officer's words become setting changes; the 3D view then reloads the model."""
    current = current_params(session, case)
    edit = ai.figure_edit(body.text, current)
    new = apply_changes(current, edit.changes)
    _store(session, request, user, case, new, {"source": "prompt", "text": body.text, "changes": edit.changes})
    return out(case, new, edit.reply)


@router.get("/figure/model.glb")
def model(request: Request, case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    glb = worker_of(request).glb(current_params(session, case))
    return Response(glb, media_type="model/gltf-binary", headers={"Cache-Control": "no-store"})


@router.post("/figure/preview.glb")
def preview(body: FigureParams, request: Request, case: Case = Depends(require_case_access)):
    """Slider drags: build what is on screen without saving it."""
    return Response(worker_of(request).glb(body), media_type="model/gltf-binary", headers={"Cache-Control": "no-store"})


@router.post("/figure/save")
def save_figure(
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Render the pencil figure and make it the case's full-body figure (shown on the case sheet)."""
    p = current_params(session, case)
    png = worker_of(request).png(p)
    rel = f"cases/{case.id}/figure-{uuid.uuid4().hex[:8]}.png"
    path = image_file(request.app.state.settings, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    body = BodyFigure(case_id=case.id, image_path=rel, prompt=f"Blender figure: {p.model_dump_json()}", created_by=user.id)
    session.add(body)
    session.commit()
    session.refresh(body)
    record(session, request, "figure_save", user, case_id=case.id, detail={"body_id": body.id, "params": p.model_dump()})
    return {"body_id": body.id, "image_url": f"/api/cases/{case.id}/body/{body.id}/image"}


@router.get("/figure.blend")
def blend(request: Request, case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    data = worker_of(request).blend(current_params(session, case))
    return Response(data, media_type="application/x-blender",
                    headers={"Content-Disposition": f'attachment; filename="{case.case_number}_figure.blend"'})
