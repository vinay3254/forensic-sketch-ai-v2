"""Kaggle 3D: the best-looking 3D figure, built on a free Kaggle GPU.

A background job (a few minutes):
1. views     the image model draws the person from the side and the back (front = the full-body image)
2. upload    the three drawings become a new version of a private Kaggle dataset
3. kaggle    a private GPU notebook (kaggle/run.py) runs Hunyuan3D-2 multi-view: drawings -> 3D shape
4. download  the shape comes back
5. paint     Blender paints the shape with the three drawings (blender_worker/paint_views.py)
6. saving    GLB + .blend saved as the case's body model, like the other "3D from image" engines

The Kaggle token is read by the kaggle client (~/.kaggle/access_token, kaggle.json or KAGGLE_API_TOKEN).
Only the drawings leave this machine, to the user's own private dataset and notebook.
"""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Protocol

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from backend.ai.client import get_ai_client
from backend.ai.prompts import VIEW_PROMPTS
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.body.routes import latest_body
from backend.config import Settings
from backend.db import get_session
from backend.errors import AppError
from backend.face.service import existing_image_file, image_file, normalize_image
from backend.figure.glb import validate_glb
from backend.figure.realistic import REPO, paths
from backend.figure.reconstruction import ReconstructIn
from backend.figure.routes import current_params
from backend.models import BodyFigure, BodyModel, Case, ModelJob, User, utcnow

ENGINE = "Hunyuan3D-2 on Kaggle, painted with the drawings"
NOTEBOOK = Path(__file__).parent / "kaggle" / "run.py"
PAINT_SCRIPT = REPO / "blender_worker" / "paint_views.py"
DATASET = "trace-3d-views"
KERNEL = "trace-3d-shape"
KERNEL_TIMEOUT_S = 45 * 60


class ShapeMaker(Protocol):
    def make_shape(self, views: dict[str, bytes], stage: Callable[[str], None]) -> bytes: ...


class Painter(Protocol):
    def paint(self, shape: bytes, views: dict[str, bytes], height_cm: float) -> tuple[bytes, bytes, str]: ...


class KaggleShapes:
    """Pushes the drawings and the notebook to the user's Kaggle account and waits for shape.glb."""

    def __init__(self):
        self._lock = threading.Lock()  # one notebook run at a time: the account has one TRACE notebook

    def make_shape(self, views: dict[str, bytes], stage: Callable[[str], None]) -> bytes:
        from kaggle.api.kaggle_api_extended import KaggleApi

        with self._lock, tempfile.TemporaryDirectory() as tmp:
            api = KaggleApi()
            api.authenticate()
            user = api.config_values["username"]
            stage("upload")
            data = Path(tmp) / "data"
            data.mkdir()
            for name, png in views.items():
                (data / f"{name}.png").write_bytes(png)
            (data / "dataset-metadata.json").write_text(json.dumps(
                {"title": "TRACE 3D views", "id": f"{user}/{DATASET}", "licenses": [{"name": "CC0-1.0"}]}))
            try:  # a new version of the dataset; the very first run creates it (private)
                api.dataset_create_version(str(data), f"TRACE {time.strftime('%Y-%m-%d %H:%M')}", quiet=True)
            except Exception:
                api.dataset_create_new(str(data), public=False, quiet=True)
            deadline = time.time() + 300
            while True:
                try:  # a dataset that is still being set up can answer 403 for a while
                    if api.dataset_status(f"{user}/{DATASET}") == "ready":
                        break
                except Exception:
                    pass
                if time.time() > deadline:
                    raise RuntimeError("Kaggle took too long to store the drawings.")
                time.sleep(5)

            stage("kaggle")
            kernel = Path(tmp) / "kernel"
            kernel.mkdir()
            shutil.copy(NOTEBOOK, kernel / "run.py")
            (kernel / "kernel-metadata.json").write_text(json.dumps({
                "id": f"{user}/{KERNEL}", "title": KERNEL, "code_file": "run.py", "language": "python",
                "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
                "dataset_sources": [f"{user}/{DATASET}"], "competition_sources": [], "kernel_sources": [],
                "machine_shape": "NvidiaTeslaT4",
            }))
            api.kernels_push(str(kernel))
            started, seen_running = time.time(), False
            while True:
                time.sleep(20)
                status = str(api.kernels_status(f"{user}/{KERNEL}").status)
                if "RUNNING" in status or "QUEUED" in status:
                    seen_running = True
                elif "COMPLETE" in status and (seen_running or time.time() - started > 120):
                    break
                elif "ERROR" in status or "CANCEL" in status:
                    raise RuntimeError(f"The Kaggle notebook stopped ({status.split('.')[-1].lower()}). "
                                       f"See kaggle.com/code/{user}/{KERNEL}")
                if time.time() - started > KERNEL_TIMEOUT_S:
                    raise RuntimeError("The Kaggle notebook took too long.")

            stage("download")
            out = Path(tmp) / "out"
            api.kernels_output(f"{user}/{KERNEL}", str(out), file_pattern=r"shape\.glb$", force=True)
            shape = out / "shape.glb"
            if not shape.is_file():
                raise RuntimeError(f"The Kaggle notebook finished without a 3D shape. See kaggle.com/code/{user}/{KERNEL}")
            return shape.read_bytes()


class ViewPainter:
    """Pose landmarks and outlines for each drawing, then Blender paints the shape with them."""

    def __init__(self, settings: Settings):
        self.settings = settings
        _, self.pose_model, self.python = paths(settings)

    def paint(self, shape: bytes, views: dict[str, bytes], height_cm: float) -> tuple[bytes, bytes, str]:
        from backend.figure.pose import NoPerson, detect

        job = self.settings.storage_dir.resolve() / "realistic" / "jobs" / uuid.uuid4().hex
        job.mkdir(parents=True)
        try:
            (job / "shape.glb").write_bytes(shape)
            for name, data in views.items():
                try:
                    pose, mask, fill = detect(data, self.pose_model)
                except NoPerson:
                    if name == "front":
                        raise RuntimeError("No standing person was found in the full-body image.")
                    continue
                (job / f"{name}_pose.json").write_text(json.dumps(pose))
                (job / f"{name}_pose_mask.png").write_bytes(mask)
                (job / f"{name}_pose_fill.png").write_bytes(fill)
            run = subprocess.run(
                [str(self.python), "-I", str(PAINT_SCRIPT), str(job / "shape.glb"), str(job), str(job / "out"), str(height_cm)],
                capture_output=True, text=True, timeout=300, cwd=job,
            )
            out = job / "out"
            if run.returncode or not (out / "figure.glb").is_file():
                raise RuntimeError(f"Blender could not paint the 3D shape. {(run.stderr or run.stdout)[-300:]}")
            summary = next((ln[8:].strip() for ln in run.stdout.splitlines() if ln.startswith("summary:")), "")
            return (out / "figure.glb").read_bytes(), (out / "figure.blend").read_bytes(), summary
        finally:
            shutil.rmtree(job, ignore_errors=True)


def kaggle_token_present() -> bool:
    home = Path.home() / ".kaggle"
    return bool(os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY")
                or (home / "access_token").is_file() or (home / "kaggle.json").is_file())


def make_kaggle(settings: Settings) -> tuple[ShapeMaker | None, Painter | None]:
    if settings.ai_mock:
        return None, None
    _, pose_model, python = paths(settings)
    painter = ViewPainter(settings) if pose_model.is_file() and python.is_file() else None
    return (KaggleShapes() if kaggle_token_present() else None), painter


router = APIRouter(prefix="/api/cases/{case_id}/figure", tags=["kaggle 3d"])


def job_out(job: ModelJob | None) -> dict | None:
    if job is None:
        return None
    return {"id": job.id, "status": job.status, "stage": job.stage, "error": job.error, "model_id": job.model_id,
            "created_at": job.created_at, "updated_at": job.updated_at}


@router.get("/kaggle")
def latest_job(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    return job_out(session.exec(
        select(ModelJob).where(ModelJob.case_id == case.id).order_by(ModelJob.id.desc())).first())


@router.post("/kaggle", status_code=202)
def start(body: ReconstructIn, request: Request, case: Case = Depends(require_case_access),
          user: User = Depends(current_user), session: Session = Depends(get_session)):
    state = request.app.state
    source = session.get(BodyFigure, body.body_id) if body.body_id else latest_body(session, case.id)
    if source is None or source.case_id != case.id:
        raise AppError("NOT_FOUND", "Draw a full-body image first.", 404)
    if state.kaggle_shapes is None:
        raise AppError("KAGGLE_OFF", "Kaggle 3D needs a Kaggle API token in ~/.kaggle/access_token. Restart after adding it.", 503)
    if state.view_painter is None:
        raise AppError("KAGGLE_OFF", "Kaggle 3D needs the pose model: run scripts.fetch_realistic_body, then restart.", 503)
    running = session.exec(select(ModelJob).where(
        ModelJob.case_id == case.id, ModelJob.status.in_(("queued", "running")))).first()
    if running:
        raise AppError("CONFLICT", "A 3D build is already running for this case.", 409)
    job = ModelJob(case_id=case.id, body_id=source.id, engine=ENGINE, created_by=user.id)
    session.add(job)
    session.commit()
    session.refresh(job)
    record(session, request, "body_kaggle", user, case_id=case.id,
           detail={"job_id": job.id, "body_id": source.id, "outcome": "started"})
    # the request is over before the job is; keep what the audit log needs from it
    req = SimpleNamespace(app=request.app, client=request.client, headers=dict(request.headers))
    threading.Thread(target=run_job, args=(req, job.id, user.id, get_ai_client(request)), daemon=True).start()
    return job_out(job)


def run_job(req, job_id: int, user_id: int, ai) -> None:
    state = req.app.state
    with Session(state.engine) as session:
        job = session.get(ModelJob, job_id)
        user = session.get(User, user_id)
        case = session.get(Case, job.case_id)
        task = state.presence.start(user_id, "POST", f"/api/cases/{case.id}/figure/kaggle")

        def stage(name: str) -> None:
            job.stage, job.status, job.updated_at = name, "running", utcnow()
            session.add(job)
            session.commit()
            state.changes.bump()

        try:
            stage("views")
            source = session.get(BodyFigure, job.body_id)
            front = existing_image_file(state.settings, source.image_path).read_bytes()
            with ThreadPoolExecutor(len(VIEW_PROMPTS)) as pool:
                jobs = {k: pool.submit(ai.edit_image, front, p) for k, p in VIEW_PROMPTS.items()}
                views = {"front": front, **{k: normalize_image(j.result(), state.settings.llm_image_size) for k, j in jobs.items()}}
            shape = state.kaggle_shapes.make_shape(views, stage)
            stage("paint")
            height = current_params(session, case).height_cm
            glb, blend, summary = state.view_painter.paint(shape, views, height)
            validate_glb(glb)
            stage("saving")
            stem = f"cases/{case.id}/kaggle3d-{uuid.uuid4().hex[:8]}"
            for suffix, data in ((".glb", glb), (".blend", blend)):
                path = image_file(state.settings, stem + suffix)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            model = BodyModel(case_id=case.id, body_id=job.body_id, mesh_path=stem + ".glb", blend_path=stem + ".blend",
                              height_cm=height, engine=ENGINE, summary=summary or None, created_by=user_id)
            session.add(model)
            session.commit()
            session.refresh(model)
            job.status, job.model_id, job.stage, job.updated_at = "done", model.id, None, utcnow()
            session.add(job)
            session.commit()
            record(session, req, "body_kaggle", user, case_id=case.id,
                   detail={"job_id": job.id, "model_id": model.id, "outcome": "ok"})
        except Exception as e:  # noqa: BLE001 - the job reports any failure; the saved model stays
            session.rollback()
            message = e.message if isinstance(e, AppError) else (str(e) or type(e).__name__)
            job.status, job.error, job.updated_at = "failed", message[:500], utcnow()
            session.add(job)
            session.commit()
            record(session, req, "body_kaggle", user, case_id=case.id,
                   detail={"job_id": job.id, "outcome": "failed", "error": message[:200]})
        finally:
            if task:
                state.presence.finish(task)
            state.changes.bump()
