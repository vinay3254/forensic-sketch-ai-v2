from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session

from backend.ai.client import AIClient, get_ai_client
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.cases.routes import VersionOut
from backend.db import get_session
from backend.errors import AppError
from backend.models import Case, User
from backend.styles import catalog
from backend.styles.service import apply_style

router = APIRouter(tags=["styles"])


class StyleIn(BaseModel):
    style: str | None = None  # a catalog key, or
    category: str | None = None  # a category plus the officer's own words
    text: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def one_choice(self) -> "StyleIn":
        if self.style is not None:
            if self.style not in catalog.BY_KEY:
                raise ValueError(f"unknown style '{self.style}'")
        elif self.category not in catalog.CATEGORY_BY_KEY or not (self.text or "").strip():
            raise ValueError("give a style, or a known category and some text")
        return self


class StyleResult(BaseModel):
    version: VersionOut
    reply: str


@router.get("/api/styles")
def list_styles(user: User = Depends(current_user)):
    return [
        {
            "key": c.key,
            "label": c.label,
            "styles": [
                {"key": s.key, "label": s.label, "image_url": f"/api/styles/{s.key}/image" if catalog.style_file(s.key) else None}
                for s in c.styles
            ],
        }
        for c in catalog.CATEGORIES
    ]


@router.get("/api/styles/{key}/image")
def style_image(key: str, user: User = Depends(current_user)):
    path = catalog.style_file(key)
    if path is None:
        raise AppError("NOT_FOUND", "Style picture not found.", 404)
    return FileResponse(path, media_type="image/png")


@router.post("/api/cases/{case_id}/style", response_model=StyleResult)
def put_style(
    body: StyleIn,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    if body.style:
        category, style = catalog.BY_KEY[body.style]
        label, change, regions = style.label, style.change, catalog.regions_of(category, style)
    else:
        category = catalog.CATEGORY_BY_KEY[body.category]
        label = change = body.text.strip()
        regions = category.regions
    detail = {"style": body.style or "custom", "category": category.key, "label": label}
    try:
        v = apply_style(session, ai, request.app.state.settings, request.app.state.face_parser, case, user,
                        category, label, change, regions)
    except AppError as e:
        record(session, request, "style_apply", user, case_id=case.id, detail={**detail, "outcome": e.code})
        raise
    record(session, request, "style_apply", user, case_id=case.id, version_id=v.id,
           detail={**detail, "outcome": "ok", "localized": v.localized})
    return StyleResult(version=VersionOut.of(v), reply=f"Applied {label}.")
