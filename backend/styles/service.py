from sqlmodel import Session

from backend.ai.client import AIClient
from backend.ai.prompts import build_style_prompt
from backend.ai.schemas import Attributes
from backend.config import Settings
from backend.errors import AppError
from backend.face.regions import Parser, localize
from backend.face.service import _commit_version, existing_image_file, latest_version, normalize_image, save_image
from backend.models import Case, FaceVersion, User
from backend.styles.catalog import Category, as_attribute


def apply_style(
    session: Session,
    ai: AIClient,
    settings: Settings,
    parser: Parser | None,
    case: Case,
    user: User,
    category: Category,
    label: str,
    change: str,
    regions: tuple[str, ...] | None,
) -> FaceVersion:
    """Put one look on the latest sketch: a new version, kept inside `regions` when the face stays put."""
    current = latest_version(session, case.id)
    if current is None:
        raise AppError("CONFLICT", "Draw a sketch first.", 409)
    prompt = build_style_prompt(category.label, change)
    before = existing_image_file(settings, current.image_path).read_bytes()
    image = normalize_image(ai.edit_image(before, prompt), settings.llm_image_size)
    localized = localize(parser, before, image, list(regions)) if regions else None
    attrs = Attributes(**current.attributes)
    if category.field:
        attrs = attrs.model_copy(update={category.field: as_attribute(change)})
    version_no = current.version_no + 1
    version = FaceVersion(
        case_id=case.id,
        parent_id=current.id,
        version_no=version_no,
        kind="refine",
        instruction=f"Style: {label}",
        uncertain=[f for f in current.uncertain or [] if f != category.field] or None,
        attributes=attrs.model_dump(),
        prompt=prompt,
        image_path=save_image(settings, case.id, version_no, localized or image),
        localized=localized is not None,
        created_by=user.id,
    )
    reply = f"Applied {label}. Click the previous version in the strip to undo."
    return _commit_version(session, settings, version, [("user", f"Style: {label}"), ("assistant", reply)])
