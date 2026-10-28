import io
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from PIL import Image
from sqlmodel import Session

from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.db import get_session
from backend.errors import AppError
from backend.export.render import stamp_footer, to_sketch, upscale
from backend.face.routes import version_of_case
from backend.face.service import existing_image_file
from backend.models import Case, User

router = APIRouter(prefix="/api/cases/{case_id}", tags=["export"])


@router.get("/versions/{version_id}/export")
def export(
    version_id: int,
    style: Literal["photo", "sketch"],
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    v = version_of_case(session, case, version_id)
    settings = request.app.state.settings
    if style == "photo":
        if not v.photo_path:
            raise AppError("CONFLICT", "Make a realistic photo of this version first.", 409)
        img = upscale(Image.open(existing_image_file(settings, v.photo_path)).convert("RGB"))
    else:
        img = to_sketch(upscale(Image.open(existing_image_file(settings, v.image_path))))
    exported_at = datetime.now(UTC).isoformat(timespec="seconds")
    img = stamp_footer(
        img,
        [f"Case {case.case_number} · Version {v.version_no}", f"Exported {exported_at} by {user.username}"],
    )
    buf = io.BytesIO()
    img.save(buf, "PNG")
    record(session, request, "export", user, case_id=case.id, version_id=v.id, detail={"style": style})
    filename = f"{case.case_number}_v{v.version_no}_{style}.png"
    return Response(
        buf.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
