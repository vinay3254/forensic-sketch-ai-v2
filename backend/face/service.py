import shutil
import uuid
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.ai.client import AIClient
from backend.ai.prompts import apply_edits, build_edit_prompt, build_image_prompt
from backend.ai.schemas import Attributes
from backend.config import Settings
from backend.errors import AppError
from backend.models import Case, ChatMessage, FaceVersion, User

FIRST_FACE_REPLY = "Here is the first face. Tell me what to change."


def image_file(settings: Settings, rel_path: str) -> Path:
    return settings.storage_dir / rel_path


def save_image(settings: Settings, case_id: int, version_no: int, data: bytes) -> str:
    # unique suffix so a failed insert can never overwrite another version's file
    rel = f"cases/{case_id}/v{version_no}-{uuid.uuid4().hex[:8]}.png"
    path = image_file(settings, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def latest_version(session: Session, case_id: int) -> FaceVersion | None:
    return session.exec(
        select(FaceVersion).where(FaceVersion.case_id == case_id).order_by(FaceVersion.version_no.desc())
    ).first()


def _commit_version(
    session: Session,
    settings: Settings,
    version: FaceVersion,
    messages: list[tuple[str, str]],
) -> FaceVersion:
    """Insert the version plus chat rows atomically; on a version_no clash, undo and report 409."""
    try:
        session.add(version)
        session.flush()
        for role, content in messages:
            session.add(ChatMessage(case_id=version.case_id, role=role, content=content, version_id=version.id))
        session.commit()
    except IntegrityError:
        session.rollback()
        image_file(settings, version.image_path).unlink(missing_ok=True)
        raise AppError("CONFLICT", "Another change is in progress. Reload and try again.", 409)
    session.refresh(version)
    return version


def _new_version_no(session: Session, case_id: int) -> tuple[int, int | None]:
    latest = latest_version(session, case_id)
    return (latest.version_no + 1, latest.id) if latest else (1, None)


def generate_face(
    session: Session, ai: AIClient, settings: Settings, case: Case, user: User, description: str
) -> FaceVersion:
    attrs = ai.extract_attributes(description)
    prompt = build_image_prompt(attrs)
    image = ai.generate_image(prompt)
    version_no, parent_id = _new_version_no(session, case.id)
    version = FaceVersion(
        case_id=case.id,
        parent_id=parent_id,
        version_no=version_no,
        kind="generate",
        instruction=description,
        attributes=attrs.model_dump(),
        prompt=prompt,
        image_path=save_image(settings, case.id, version_no, image),
        created_by=user.id,
    )
    return _commit_version(session, settings, version, [("user", description), ("assistant", FIRST_FACE_REPLY)])


def refine_face(
    session: Session, ai: AIClient, settings: Settings, case: Case, user: User, message: str
) -> tuple[FaceVersion | None, str]:
    current = latest_version(session, case.id)
    if current is None:
        raise AppError("CONFLICT", "Generate a face first.", 409)
    plan = ai.parse_edit(message, Attributes(**current.attributes))
    if plan.needs_clarification or not plan.edits:
        session.add(ChatMessage(case_id=case.id, role="user", content=message))
        session.add(ChatMessage(case_id=case.id, role="assistant", content=plan.reply))
        session.commit()
        return None, plan.reply
    attrs = apply_edits(Attributes(**current.attributes), plan.edits)
    prompt = build_edit_prompt(plan.edits)
    image = ai.edit_image(image_file(settings, current.image_path).read_bytes(), prompt)
    version = FaceVersion(
        case_id=case.id,
        parent_id=current.id,
        version_no=current.version_no + 1,
        kind="refine",
        instruction=message,
        attributes=attrs.model_dump(),
        prompt=prompt,
        image_path=save_image(settings, case.id, current.version_no + 1, image),
        created_by=user.id,
    )
    return _commit_version(session, settings, version, [("user", message), ("assistant", plan.reply)]), plan.reply


def revert_face(session: Session, settings: Settings, case: Case, user: User, version_id: int) -> FaceVersion:
    source = session.get(FaceVersion, version_id)
    if source is None or source.case_id != case.id:
        raise AppError("NOT_FOUND", "Version not found.", 404)
    version_no, parent_id = _new_version_no(session, case.id)
    rel = f"cases/{case.id}/v{version_no}-{uuid.uuid4().hex[:8]}.png"
    shutil.copyfile(image_file(settings, source.image_path), image_file(settings, rel))
    version = FaceVersion(
        case_id=case.id,
        parent_id=parent_id,
        version_no=version_no,
        kind="revert",
        instruction=f"Revert to v{source.version_no}",
        attributes=dict(source.attributes),
        prompt=source.prompt,
        image_path=rel,
        created_by=user.id,
    )
    return _commit_version(session, settings, version, [("assistant", f"Reverted to version {source.version_no}.")])
