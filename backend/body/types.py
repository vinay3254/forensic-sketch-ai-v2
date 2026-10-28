"""Five fixed body-type reference figures (scripts/make_body_types.py), shown as a chart
the officer and witness can point at, and printed on the case sheet."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from backend.auth.deps import current_user
from backend.errors import AppError

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "body_types"
BODY_TYPES = [("slim", "Slim"), ("athletic", "Athletic"), ("overweight", "Overweight"), ("heavy", "Heavy"), ("obese", "Obese")]

router = APIRouter(prefix="/api/body-types", tags=["body"], dependencies=[Depends(current_user)])


def body_type_file(key: str) -> Path | None:
    if key not in dict(BODY_TYPES):  # only fixed names ever reach the filesystem
        return None
    path = ASSETS / f"{key}.png"
    return path if path.is_file() else None


@router.get("")
def list_body_types():
    return [
        {"key": k, "label": label, "image_url": f"/api/body-types/{k}/image"}
        for k, label in BODY_TYPES
        if body_type_file(k)
    ]


@router.get("/{key}/image")
def body_type_image(key: str):
    path = body_type_file(key)
    if path is None:
        raise AppError("NOT_FOUND", "Body type not found.", 404)
    return FileResponse(path, media_type="image/png")
