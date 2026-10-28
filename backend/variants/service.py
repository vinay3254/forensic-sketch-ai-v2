import uuid

from sqlmodel import Session

from backend.ai.client import AIClient
from backend.ai.prompts import VARIANTS, build_variant_prompt
from backend.config import Settings
from backend.face.regions import Parser, localize
from backend.face.service import existing_image_file, image_file, normalize_image
from backend.models import Case, FaceVersion, User, Variant


def create_variant(
    session: Session,
    ai: AIClient,
    settings: Settings,
    parser: Parser | None,
    case: Case,
    user: User,
    version: FaceVersion,
    kind: str,
) -> Variant:
    prompt = build_variant_prompt(kind)
    before = existing_image_file(settings, version.image_path).read_bytes()
    image = normalize_image(ai.edit_image(before, prompt), settings.llm_image_size)
    regions = VARIANTS[kind][2]
    localized = localize(parser, before, image, regions) if regions else None
    rel = f"cases/{case.id}/variant-{kind}-{uuid.uuid4().hex[:8]}.png"
    path = image_file(settings, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(localized or image)
    variant = Variant(
        case_id=case.id, version_id=version.id, kind=kind, image_path=rel, prompt=prompt,
        localized=localized is not None, created_by=user.id,
    )
    session.add(variant)
    session.commit()
    session.refresh(variant)
    return variant
