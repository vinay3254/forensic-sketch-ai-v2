import io
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from PIL import Image
from sqlmodel import Session, select

from backend.ai.prompts import VARIANTS
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.body.routes import latest_body
from backend.body.types import BODY_TYPES, body_type_file
from backend.db import get_session
from backend.errors import AppError
from backend.face.routes import version_of_case
from backend.face.service import image_file, latest_version
from backend.models import Case, User, Variant
from backend.sheet.render import SheetData, render_sheet

router = APIRouter(prefix="/api/cases/{case_id}", tags=["sheet"])


def load(settings, rel: str) -> Image.Image | None:
    path = image_file(settings, rel)
    return Image.open(path) if path.is_file() else None  # a missing extra is left off, not an error


@router.get("/sheet")
def case_sheet(
    request: Request,
    version_id: int | None = None,
    format: Literal["png", "pdf"] = "png",
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    settings = request.app.state.settings
    v = version_of_case(session, case, version_id) if version_id else latest_version(session, case.id)
    if v is None:
        raise AppError("CONFLICT", "Generate a sketch first.", 409)
    sketch = load(settings, v.image_path)
    if sketch is None:
        raise AppError("NOT_FOUND", "The image file for this version is missing.", 404)
    variants = session.exec(select(Variant).where(Variant.case_id == case.id).order_by(Variant.id)).all()
    body = latest_body(session, case.id)
    data = SheetData(
        case_number=case.case_number,
        title=case.title,
        details=case.details or {},
        sketch=sketch,
        version_no=v.version_no,
        attributes=v.attributes,
        uncertain=v.uncertain or [],
        exported_by=user.username,
        exported_at=datetime.now(UTC).isoformat(timespec="seconds"),
        variants=[(VARIANTS[x.kind][0], img) for x in variants if (img := load(settings, x.image_path))],
        body=load(settings, body.image_path) if body else None,
        body_types=[(label, Image.open(p)) for key, label in BODY_TYPES if (p := body_type_file(key))],
    )
    buf = io.BytesIO()
    page = render_sheet(data)
    if format == "pdf":
        page.save(buf, "PDF", resolution=300)
    else:
        page.save(buf, "PNG", dpi=(300, 300))
    record(session, request, "export", user, case_id=case.id, version_id=v.id, detail={"style": "sheet", "format": format})
    return Response(
        buf.getvalue(),
        media_type="application/pdf" if format == "pdf" else "image/png",
        headers={"Content-Disposition": f'attachment; filename="{case.case_number}_v{v.version_no}_sheet.{format}"'},
    )
