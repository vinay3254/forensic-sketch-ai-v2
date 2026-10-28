"""Witnesses can speak in their own language. Their words are stored verbatim; an English
translation is stored beside them and is what the sketch is made from."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from backend.ai.client import AIClient, get_ai_client
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.db import get_session
from backend.models import Case, User

# speech-recognition codes (Chrome's Web Speech API) -> language name for the translator
LANGUAGES = {
    "en-IN": "English", "en-US": "English", "hi-IN": "Hindi", "kn-IN": "Kannada", "te-IN": "Telugu",
    "ta-IN": "Tamil", "ml-IN": "Malayalam", "mr-IN": "Marathi", "bn-IN": "Bengali", "gu-IN": "Gujarati",
}
MAX_TEXT = 2000


def check_language(code: str | None) -> str | None:
    if code is not None and code not in LANGUAGES:
        raise ValueError(f"unsupported language '{code}'")
    return code


def needs_translation(code: str | None) -> bool:
    return code is not None and LANGUAGES[code] != "English"


def to_english(ai: AIClient, text: str, code: str | None) -> str:
    return ai.translate(text, LANGUAGES[code]) if needs_translation(code) and text.strip() else text


router = APIRouter(tags=["translate"])


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    lang: str

    _lang = field_validator("lang")(classmethod(lambda cls, v: check_language(v)))


@router.post("/api/cases/{case_id}/translate")
def translate(
    body: TranslateIn,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    """English for the officer to check; nothing is stored until the interview is saved."""
    english = to_english(ai, body.text, body.lang)
    if needs_translation(body.lang):
        record(session, request, "translate", user, case_id=case.id, detail={"lang": body.lang, "chars": len(body.text)})
    return {"english": english}
