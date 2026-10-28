"""Authenticated, persisted background jobs for LLM-driven Blender modeling."""

import logging
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.body.routes import latest_body
from backend.db import get_session
from backend.errors import AppError
from backend.face.service import existing_image_file, image_file, latest_version
from backend.figure.glb import validate_glb
from backend.figure.routes import current_params
from backend.models import BlenderJob, BodyFigure, BodyModel, Case, User

router = APIRouter(prefix='/api/cases/{case_id}/figure/blender-jobs', tags=['Blender modeling'])
ACTIVE = {'queued', 'drafting', 'building', 'opening'}
log = logging.getLogger(__name__)


class BuildIn(BaseModel):
    body_id: int | None = Field(default=None, gt=0)
    prompt: str = Field(min_length=1, max_length=2000)


class JobOut(BaseModel):
    id: int
    body_id: int
    status: Literal['queued', 'drafting', 'building', 'opening', 'complete', 'failed']
    model_id: int | None
    error: str | None
    desktop_opened: bool
    desktop_error: str | None
    created_at: datetime

    @classmethod
    def of(cls, job):
        return cls.model_validate(job, from_attributes=True)


def update_job(state, job_id, **changes):
    with Session(state.engine) as session:
        job = session.get(BlenderJob, job_id)
        for key, value in changes.items():
            setattr(job, key, value)
        session.add(job)
        session.commit()


def run_job(state, job_id, case_id, body_id, user_id, image, facts, prompt, request):
    try:
        with state.blender_build_lock:
            update_job(state, job_id, status='drafting')
            draft = state.blender_builder.draft(image, facts, prompt)
            update_job(state, job_id, status='building')
            rel = f'cases/{case_id}/blender-{uuid.uuid4().hex}'
            directory = image_file(state.settings, rel)
            state.blender_builder.build(draft, directory)
            mesh = (directory / 'model.glb').read_bytes()
            try:
                validate_glb(mesh)
            except ValueError:
                raise AppError('INVALID_MODEL', 'Blender returned an empty or invalid model. Try another prompt.', 422)
            with Session(state.engine) as session:
                model = BodyModel(case_id=case_id, body_id=body_id, mesh_path=f'{rel}/model.glb',
                                  blend_path=f'{rel}/model.blend', script_path=f'{rel}/draft.py',
                                  height_cm=facts['height_cm'], engine='LLM Blender modeling', summary=draft.summary,
                                  created_by=user_id)
                session.add(model)
                session.commit()
                session.refresh(model)
                model_id = model.id
                user = session.get(User, user_id)
                record(session, request, 'blender_model_complete', user, case_id=case_id,
                       detail={'job_id': job_id, 'model_id': model_id, 'body_id': body_id})
            update_job(state, job_id, status='opening', model_id=model_id)
            opened, error = False, None
            try:
                if state.figure_worker is None:
                    raise AppError('FIGURE_OFF', 'Open Blender for TRACE, then use Open in Blender.', 503)
                state.figure_worker.import_glb(mesh)
                opened = True
            except Exception as exc:
                error = exc.message if isinstance(exc, AppError) else 'Desktop delivery failed. Use Open in Blender to retry.'
            update_job(state, job_id, status='complete', desktop_opened=opened, desktop_error=error)
    except Exception as exc:
        log.exception('Blender modeling job %s failed', job_id)
        message = exc.message if isinstance(exc, AppError) else 'Blender modeling failed. Your previous model is still saved.'
        update_job(state, job_id, status='failed', error=message)
    finally:
        state.blender_slots.release()


def process_token(pid):
    try:
        start = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        return f'{boot}:{pid}:{start}'
    except (OSError, IndexError):
        return None


def recover_interrupted(session, job):
    if job and job.status in ACTIVE:
        if not job.worker_token or process_token(job.worker_pid) != job.worker_token:
            job.status = 'failed'
            job.error = 'Build was interrupted by a server restart. Start again.'
            session.add(job)
            session.commit()
    return job


@router.get('/latest', response_model=JobOut | None)
def latest_job(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    job = session.exec(select(BlenderJob).where(BlenderJob.case_id == case.id).order_by(BlenderJob.id.desc())).first()
    recover_interrupted(session, job)
    return JobOut.of(job) if job else None


@router.post('', response_model=JobOut, status_code=202)
def start_job(body: BuildIn, background: BackgroundTasks, request: Request,
              case: Case = Depends(require_case_access), user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    if not body.prompt.strip():
        raise AppError('VALIDATION', 'Describe the model you want to build.', 422)
    source = session.get(BodyFigure, body.body_id) if body.body_id else latest_body(session, case.id)
    if source is None or source.case_id != case.id:
        raise AppError('NOT_FOUND', 'Draw a full-body reference first.', 404)
    previous = session.exec(select(BlenderJob).where(BlenderJob.case_id == case.id).order_by(BlenderJob.id.desc())).first()
    recover_interrupted(session, previous)
    if previous and previous.status in ACTIVE:
        raise AppError('BLENDER_BUSY', 'This case already has a Blender build in progress.', 409)
    state = request.app.state
    image = existing_image_file(state.settings, source.image_path).read_bytes()
    version = latest_version(session, case.id)
    facts = {'height_cm': current_params(session, case).height_cm, 'details': case.details or {},
             'attributes': version.attributes if version else {}}
    if not state.blender_slots.acquire(blocking=False):
        raise AppError('BLENDER_BUSY', 'Blender build queue is full. Try again after the current builds finish.', 429)
    try:
        job = BlenderJob(case_id=case.id, body_id=source.id, prompt=body.prompt.strip(),
                         worker_pid=os.getpid(), worker_token=process_token(os.getpid()), created_by=user.id)
        session.add(job)
        session.commit()
        session.refresh(job)
        record(session, request, 'blender_model_start', user, case_id=case.id,
               detail={'job_id': job.id, 'body_id': source.id, 'prompt': job.prompt})
        background.add_task(run_job, state, job.id, case.id, source.id, user.id, image, facts, job.prompt, request)
        return JobOut.of(job)
    except IntegrityError:
        session.rollback()
        state.blender_slots.release()
        raise AppError('BLENDER_BUSY', 'This case already has a Blender build in progress.', 409)
    except Exception:
        state.blender_slots.release()
        raise
