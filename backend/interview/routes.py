from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from backend.ai.client import AIClient, get_ai_client
from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.cases.details import prefill_from_interview
from backend.cases.routes import VersionOut
from backend.db import get_session
from backend.errors import AppError
from backend.face import service as face_service
from backend.interview.assist import find_coverage
from backend.interview.questions import EXTRAS, FEATURES, FREE_RECALL, PROMPTS
from backend.interview.transcript import has_content, in_question_order, transcript_hash
from backend.models import Case, Interview, User, utcnow
from backend.translate import check_language, needs_translation

router = APIRouter(tags=["interview"])

MAX_TEXT = 2000

Source = Literal["typed", "speech", "mixed"]


class AnswerIn(BaseModel):
    key: str
    answer: str = Field(default="", max_length=MAX_TEXT)
    status: Literal["remembered", "uncertain", "unknown"] | None = None
    source: Source | None = None
    lang: str | None = None  # speech-recognition code of the language the witness used
    english: str | None = Field(default=None, max_length=MAX_TEXT * 2)  # translation, for non-English words

    _lang = field_validator("lang")(classmethod(lambda cls, v: check_language(v)))

    @field_validator("key")
    @classmethod
    def known_key(cls, key: str) -> str:
        if key not in PROMPTS:
            raise ValueError(f"unknown question '{key}'")
        return key


class DraftIn(BaseModel):
    free_recall: str = Field(default="", max_length=MAX_TEXT)
    free_recall_source: Source | None = None
    free_recall_lang: str | None = None
    free_recall_english: str | None = Field(default=None, max_length=MAX_TEXT * 2)
    answers: list[AnswerIn] = []

    _lang = field_validator("free_recall_lang")(classmethod(lambda cls, v: check_language(v)))

    @field_validator("answers")
    @classmethod
    def one_answer_per_question(cls, answers: list[AnswerIn]) -> list[AnswerIn]:
        keys = [a.key for a in answers]
        if len(keys) != len(set(keys)):
            raise ValueError("each question can be answered only once")
        return answers


class ConfirmIn(BaseModel):
    witness_confirmed: Literal[True]  # the officer ticks this after reading the transcript back to the witness


class InterviewOut(BaseModel):
    id: int
    case_id: int
    status: str
    free_recall: str
    free_recall_source: str | None
    free_recall_lang: str | None = None
    free_recall_english: str | None = None
    answers: list
    created_by: int
    created_at: datetime
    confirmed_by: int | None
    confirmed_at: datetime | None
    transcript_hash: str | None


def interview_of_case(session: Session, case: Case, interview_id: int) -> Interview:
    iv = session.get(Interview, interview_id)
    if iv is None or iv.case_id != case.id:
        raise AppError("NOT_FOUND", "Interview not found.", 404)
    return iv


@router.get("/api/interview/questions")
def questions(user: User = Depends(current_user)):
    return {"free_recall": FREE_RECALL, "features": FEATURES, "extras": EXTRAS}


@router.post("/api/cases/{case_id}/interviews", response_model=InterviewOut)
def start(
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    iv = Interview(case_id=case.id, created_by=user.id)
    session.add(iv)
    session.commit()
    session.refresh(iv)
    record(session, request, "interview_start", user, case_id=case.id, detail={"interview_id": iv.id})
    return InterviewOut(**iv.model_dump())


@router.get("/api/cases/{case_id}/interviews", response_model=list[InterviewOut])
def list_interviews(case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    rows = session.exec(select(Interview).where(Interview.case_id == case.id).order_by(Interview.id.desc())).all()
    return [InterviewOut(**iv.model_dump()) for iv in rows]


@router.get("/api/cases/{case_id}/interviews/{interview_id}", response_model=InterviewOut)
def read(interview_id: int, case: Case = Depends(require_case_access), session: Session = Depends(get_session)):
    return InterviewOut(**interview_of_case(session, case, interview_id).model_dump())


@router.put("/api/cases/{case_id}/interviews/{interview_id}", response_model=InterviewOut)
def save_draft(
    interview_id: int,
    body: DraftIn,
    case: Case = Depends(require_case_access),
    session: Session = Depends(get_session),
):
    """Autosave. Words are stored exactly as entered; the prompt always comes from the bank."""
    iv = interview_of_case(session, case, interview_id)
    if iv.status != "draft":
        raise AppError("CONFLICT", "This interview has been confirmed and can no longer be changed.", 409)
    iv.free_recall = body.free_recall
    iv.free_recall_source = body.free_recall_source
    # language fields only for words in another language, so English transcripts hash as before
    other = needs_translation(body.free_recall_lang)
    iv.free_recall_lang = body.free_recall_lang if other else None
    iv.free_recall_english = body.free_recall_english if other else None
    iv.answers = in_question_order([_answer(a) for a in body.answers])
    session.add(iv)
    session.commit()
    session.refresh(iv)
    return InterviewOut(**iv.model_dump())


def _answer(a: AnswerIn) -> dict:
    row = {"key": a.key, "prompt": PROMPTS[a.key], "answer": a.answer, "status": a.status, "source": a.source}
    if needs_translation(a.lang):
        row |= {"lang": a.lang, "english": a.english}
    return row


def untranslated(iv: dict) -> bool:
    if iv.get("free_recall_lang") and iv["free_recall"].strip() and not (iv.get("free_recall_english") or "").strip():
        return True
    return any(a.get("lang") and a["answer"].strip() and not (a.get("english") or "").strip() for a in iv["answers"])


class AssistOut(BaseModel):
    covered: dict[str, list[str]]  # feature key -> exact quotes from the free account


@router.post("/api/cases/{case_id}/interviews/{interview_id}/assist", response_model=AssistOut)
def assist(
    interview_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    """Option B, off by default in the UI: point at the parts of the free account that already cover
    each feature. Nothing is stored; an AI failure leaves the interview as it was."""
    iv = interview_of_case(session, case, interview_id)
    if iv.status != "draft":
        raise AppError("CONFLICT", "This interview has been confirmed and can no longer be changed.", 409)
    if not iv.free_recall.strip():
        raise AppError("VALIDATION", "Record the witness's free account first.", 422)
    covered = find_coverage(ai, iv.free_recall)
    record(
        session, request, "interview_assist", user, case_id=case.id,
        detail={"interview_id": iv.id, "keys": list(covered)},
    )
    return AssistOut(covered=covered)


@router.post("/api/cases/{case_id}/interviews/{interview_id}/confirm", response_model=InterviewOut)
def confirm(
    interview_id: int,
    body: ConfirmIn,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """The witness has reviewed the transcript: lock it and put its fingerprint on the audit chain."""
    iv = interview_of_case(session, case, interview_id)
    if iv.status != "draft":
        raise AppError("CONFLICT", "This interview has already been confirmed.", 409)
    if not has_content(iv.model_dump()):
        raise AppError("VALIDATION", "Record at least the free account or one answer before confirming.", 422)
    if untranslated(iv.model_dump()):
        raise AppError("TRANSLATION_MISSING", "Translate every answer given in another language before confirming.", 422)
    iv.transcript_hash = transcript_hash(iv.model_dump())
    iv.status = "confirmed"
    iv.confirmed_by = user.id
    iv.confirmed_at = utcnow()
    session.add(iv)
    session.commit()
    session.refresh(iv)
    record(
        session, request, "interview_confirm", user, case_id=case.id,
        detail={"interview_id": iv.id, "transcript_hash": iv.transcript_hash},
    )
    return InterviewOut(**iv.model_dump())


@router.post("/api/cases/{case_id}/interviews/{interview_id}/generate", response_model=VersionOut)
def generate_from_interview(
    interview_id: int,
    request: Request,
    case: Case = Depends(require_case_access),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    ai: AIClient = Depends(get_ai_client),
):
    """Draw the sketch from the confirmed transcript. A failure leaves the interview confirmed; retrying is safe."""
    iv = interview_of_case(session, case, interview_id)
    if iv.status != "confirmed":
        raise AppError("CONFLICT", "The witness must confirm the transcript before a sketch is generated.", 409)
    try:
        v = face_service.generate_face(session, ai, request.app.state.settings, case, user, interview=iv)
    except AppError as e:
        record(session, request, "generate", user, case_id=case.id, detail={"outcome": e.code, "interview_id": iv.id})
        raise
    record(
        session, request, "generate", user, case_id=case.id, version_id=v.id,
        detail={"outcome": "ok", "interview_id": iv.id},
    )
    details = prefill_from_interview(case.details or {}, iv.answers)
    if details != (case.details or {}):
        changed = sorted(k for k in details if details[k] != (case.details or {}).get(k))
        case.details = details
        session.add(case)
        session.commit()
        record(session, request, "case_update", user, case_id=case.id, detail={"keys": changed, "interview_id": iv.id})
    return VersionOut.of(v)
