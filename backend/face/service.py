import io
import shutil
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.ai.client import AIClient
from backend.ai.prompts import apply_edits, build_edit_prompt, build_image_prompt, build_photo_prompt
from backend.ai.schemas import Attributes
from backend.config import Settings
from backend.face.regions import Parser, localize
from backend.errors import AppError
from backend.interview.transcript import fields_with_status, render_description
from backend.models import Case, ChatMessage, FaceVersion, Interview, User

FIRST_FACE_REPLY = "Here is the first face. Tell me what to change."
NEW_FACE_REPLY = "Here is a new face from the updated description. Tell me what to change."


def image_file(settings: Settings, rel_path: str) -> Path:
    return settings.storage_dir / rel_path


def existing_image_file(settings: Settings, rel_path: str) -> Path:
    path = image_file(settings, rel_path)
    if not path.is_file():
        raise AppError("NOT_FOUND", "The image file for this version is missing.", 404)
    return path


def normalize_image(data: bytes, size: str, mode: str = "L") -> bytes:
    """Return the AI image as PNG in `mode` ("L" for sketches, "RGB" for photos),
    centre-cropped to the configured aspect ratio.

    Providers differ: some send JPEG, some ignore the requested size (Codex returns
    landscape). Unreadable bytes are rejected before anything is stored."""
    try:
        with Image.open(io.BytesIO(data)) as src:
            img = src.convert(mode)  # sketches stay black and white even if the model adds a tint
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise AppError("AI_UNAVAILABLE", "The image service returned an unreadable image. Try again.", 503)
    w, h = (int(n) for n in size.lower().split("x"))
    target = w / h
    if img.width / img.height > target:  # too wide: trim the sides
        new_w = round(img.height * target)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    elif img.width / img.height < target:  # too tall: trim top and bottom
        new_h = round(img.width / target)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


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
    except Exception:
        session.rollback()
        image_file(settings, version.image_path).unlink(missing_ok=True)
        raise
    session.refresh(version)
    return version


def _new_version_no(session: Session, case_id: int) -> tuple[int, int | None]:
    latest = latest_version(session, case_id)
    return (latest.version_no + 1, latest.id) if latest else (1, None)


def generate_face(
    session: Session,
    ai: AIClient,
    settings: Settings,
    case: Case,
    user: User,
    description: str | None = None,
    interview: Interview | None = None,
) -> FaceVersion:
    """First (or replacement) sketch, from a typed description or a confirmed interview."""
    uncertain = None
    if interview is not None:
        iv = interview.model_dump()
        description = render_description(iv)
        attrs = ai.extract_attributes(description)
        # a feature the witness said they don't remember stays blank, whatever the extractor read
        attrs = attrs.model_copy(update={f: None for f in fields_with_status(iv, "unknown")})
        uncertain = fields_with_status(iv, "uncertain")
    else:
        attrs = ai.extract_attributes(description)
    prompt = build_image_prompt(attrs)
    image = normalize_image(ai.generate_image(prompt), settings.llm_image_size)
    version_no, parent_id = _new_version_no(session, case.id)
    version = FaceVersion(
        case_id=case.id,
        parent_id=parent_id,
        version_no=version_no,
        kind="generate",
        instruction=f"From witness interview #{interview.id}" if interview else description,
        attributes=attrs.model_dump(),
        prompt=prompt,
        image_path=save_image(settings, case.id, version_no, image),
        created_by=user.id,
        interview_id=interview.id if interview else None,
        uncertain=uncertain,
    )
    reply = FIRST_FACE_REPLY if version_no == 1 else NEW_FACE_REPLY
    said = f"Witness interview #{interview.id} (confirmed)" if interview else description
    return _commit_version(session, settings, version, [("user", said), ("assistant", reply)])


def refine_face(
    session: Session,
    ai: AIClient,
    settings: Settings,
    case: Case,
    user: User,
    message: str,
    parser: Parser | None = None,
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
    before = existing_image_file(settings, current.image_path).read_bytes()
    image = normalize_image(ai.edit_image(before, prompt), settings.llm_image_size)
    localized = localize(parser, before, image, [e.region for e in plan.edits])
    version = FaceVersion(
        case_id=case.id,
        parent_id=current.id,
        version_no=current.version_no + 1,
        kind="refine",
        instruction=message,
        # the witness has just described the edited features, so they are no longer flagged
        uncertain=[f for f in current.uncertain or [] if f not in {e.region for e in plan.edits}] or None,
        attributes=attrs.model_dump(),
        prompt=prompt,
        image_path=save_image(settings, case.id, current.version_no + 1, localized or image),
        localized=localized is not None,
        created_by=user.id,
    )
    return _commit_version(session, settings, version, [("user", message), ("assistant", plan.reply)]), plan.reply


def revert_face(session: Session, settings: Settings, case: Case, user: User, version_id: int) -> FaceVersion:
    source = session.get(FaceVersion, version_id)
    if source is None or source.case_id != case.id:
        raise AppError("NOT_FOUND", "Version not found.", 404)
    version_no, parent_id = _new_version_no(session, case.id)
    rel = f"cases/{case.id}/v{version_no}-{uuid.uuid4().hex[:8]}.png"
    shutil.copyfile(existing_image_file(settings, source.image_path), image_file(settings, rel))
    version = FaceVersion(
        case_id=case.id,
        parent_id=parent_id,
        version_no=version_no,
        kind="revert",
        instruction=f"Revert to v{source.version_no}",
        attributes=dict(source.attributes),
        uncertain=source.uncertain,
        prompt=source.prompt,
        image_path=rel,
        created_by=user.id,
    )
    return _commit_version(session, settings, version, [("assistant", f"Reverted to version {source.version_no}.")])


def make_photo(session: Session, ai: AIClient, settings: Settings, version: FaceVersion) -> FaceVersion:
    """Turn a sketch version into a realistic colour photo, once; later calls reuse the file."""
    if version.photo_path and image_file(settings, version.photo_path).is_file():
        return version
    sketch = existing_image_file(settings, version.image_path).read_bytes()
    photo = ai.edit_image(sketch, build_photo_prompt(Attributes(**version.attributes)))
    photo = normalize_image(photo, settings.llm_image_size, mode="RGB")
    rel = f"cases/{version.case_id}/v{version.version_no}-photo-{uuid.uuid4().hex[:8]}.png"
    path = image_file(settings, rel)
    path.write_bytes(photo)
    try:
        version.photo_path = rel
        session.add(version)
        session.commit()
    except Exception:
        session.rollback()
        path.unlink(missing_ok=True)
        raise
    session.refresh(version)
    return version
