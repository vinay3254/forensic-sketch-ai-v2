"""Realistic body: a MakeHuman (MPFB2) human fitted to the full-body picture, built in Blender.

The image model draws the same person from the side and from the back; pose detection finds the
landmarks and outline in each view. Blender then poses the body like the picture, stretches it
between landmarks so eyes, shoulders, hips, knees and ankles sit at the picture's heights, fits
every slice to the front outline (width) and side outline (depth), and textures each surface from
the view that faces it. The result is saved as a BodyModel, like the other "3D from image" engines.
"""

import json
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from backend.ai.client import AIClient, get_ai_client
from backend.ai.prompts import VIEW_PROMPTS
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.body.routes import latest_body
from backend.config import Settings
from backend.db import get_session
from backend.errors import AppError
from backend.face.service import existing_image_file, image_file, normalize_image
from backend.figure.glb import validate_glb
from backend.figure.params import FigureParams
from backend.figure.reconstruction import BodyModelOut, ReconstructIn
from backend.figure.routes import current_params
from backend.models import BodyFigure, BodyModel, Case, User

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "blender_worker" / "realistic_body.py"
ENGINE = "Realistic body (MPFB2, front/side/back views)"
BUILD_TIMEOUT_S = 300


class RealisticBuilder(Protocol):
    def build(self, front: bytes, views: dict[str, bytes], params: FigureParams) -> tuple[bytes, bytes, str]:
        """(GLB, .blend, one-line summary)"""


def paths(settings: Settings) -> tuple[Path, Path, Path]:
    root = settings.storage_dir.resolve() / "realistic"  # absolute: Blender runs inside the job folder
    python = Path(settings.blender_python)
    return root / "mpfb2" / "src", root / "pose_landmarker_heavy.task", python if python.is_absolute() else REPO / python


class LiveRealisticBuilder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mpfb, self.pose_model, self.python = paths(settings)

    def build(self, front: bytes, views: dict[str, bytes], params: FigureParams) -> tuple[bytes, bytes, str]:
        from backend.figure.pose import NoPerson, detect

        job = self.settings.storage_dir.resolve() / "realistic" / "jobs" / uuid.uuid4().hex
        job.mkdir(parents=True)
        try:
            for name, data in {"front": front, **views}.items():
                try:
                    pose, mask, fill = detect(data, self.pose_model)
                except NoPerson:
                    if name == "front":
                        raise AppError("NO_PERSON", "No standing person was found in the full-body image.", 422)
                    continue  # a failed extra view just leaves those surfaces to the front picture
                (job / f"{name}_pose.json").write_text(json.dumps(pose))
                (job / f"{name}_pose_mask.png").write_bytes(mask)
                (job / f"{name}_pose_fill.png").write_bytes(fill)
            # MPFB2 is MakeHuman's Blender add-on; male is 1 there, female 0
            args = [str(self.python), "-I", str(SCRIPT), str(self.mpfb), str(job), str(job / "out"),
                    str(params.height_cm), str(1 - params.gender), str(params.age), str(params.build)]
            try:
                run = subprocess.run(args, capture_output=True, text=True, timeout=BUILD_TIMEOUT_S, cwd=job)
            except subprocess.TimeoutExpired:
                raise AppError("BUILD_FAILED", "Building the realistic body took too long.", 504)
            out = job / "out"
            if run.returncode != 0 or not (out / "figure.glb").is_file():
                tail = (run.stderr or run.stdout)[-400:]
                raise AppError("BUILD_FAILED", f"Blender could not build the realistic body. {tail}", 502)
            summary = next((ln for ln in run.stdout.splitlines() if ln.startswith("summary:")), "summary:")[8:].strip()
            return (out / "figure.glb").read_bytes(), (out / "figure.blend").read_bytes(), summary
        finally:
            shutil.rmtree(job, ignore_errors=True)


def make_realistic_builder(settings: Settings) -> RealisticBuilder | None:
    mpfb, model, python = paths(settings)
    if settings.ai_mock or not (mpfb.is_dir() and model.is_file() and python.is_file()):
        return None
    return LiveRealisticBuilder(settings)


router = APIRouter(prefix="/api/cases/{case_id}/figure", tags=["realistic body"])


@router.post("/realistic", response_model=BodyModelOut)
def build_realistic(
    body: ReconstructIn,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    source = session.get(BodyFigure, body.body_id) if body.body_id else latest_body(session, case.id)
    if source is None or source.case_id != case.id:
        raise AppError("NOT_FOUND", "Draw a full-body image first.", 404)
    builder: RealisticBuilder | None = request.app.state.realistic_builder
    if builder is None:
        raise AppError(
            "REALISTIC_OFF",
            "The realistic body needs MPFB2 and the pose model: run scripts.fetch_realistic_body, then restart.",
            503,
        )
    settings = request.app.state.settings
    params = current_params(session, case)
    detail = {"body_id": source.id}
    try:
        front = existing_image_file(settings, source.image_path).read_bytes()
        # the same person from the side and the back, drawn by the image model in parallel
        with ThreadPoolExecutor(len(VIEW_PROMPTS)) as pool:
            jobs = {k: pool.submit(ai.edit_image, front, p) for k, p in VIEW_PROMPTS.items()}
            views = {k: normalize_image(j.result(), settings.llm_image_size) for k, j in jobs.items()}
        glb, blend, summary = builder.build(front, views, params)
        try:
            validate_glb(glb)
        except ValueError:
            raise AppError("INVALID_MODEL", "The realistic body build produced an invalid 3D model.", 502)
    except AppError as e:
        record(session, request, "body_realistic", user, case_id=case.id, detail={**detail, "outcome": e.code})
        raise
    stem = f"cases/{case.id}/realistic-{uuid.uuid4().hex[:8]}"
    for suffix, data in ((".glb", glb), (".blend", blend)):
        path = image_file(settings, stem + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    model = BodyModel(case_id=case.id, body_id=source.id, mesh_path=stem + ".glb", blend_path=stem + ".blend",
                      height_cm=params.height_cm, engine=ENGINE, summary=summary or None, created_by=user.id)
    session.add(model)
    session.commit()
    session.refresh(model)
    record(session, request, "body_realistic", user, case_id=case.id,
           detail={**detail, "model_id": model.id, "outcome": "ok"})
    return BodyModelOut.of(model)
