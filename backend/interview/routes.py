from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from backend.audit.logger import record
from backend.auth.deps import current_user, require_case_access
from backend.db import get_session
from backend.errors import AppError
from backend.interview.questions import EXTRAS, FEATURES, FREE_RECALL, PROMPTS
from backend.models import Case, Interview, User

router = APIRouter(tags=["interview"])

MAX_TEXT = 2000

Source = Literal["typed", "speech", "mixed"]


class AnswerIn(BaseModel):
    key: str
    answer: str = Field(default="", max_length=MAX_TEXT)
    status: Literal["remembered", "uncertain", "unknown"] | None = None
    source: Source | None = None

    @field_validator("key")
    @classmethod
    def known_key(cls, key: str) -> str:
        if key not in PROMPTS:
            raise ValueError(f"unknown question '{key}'")
        return key


class DraftIn(BaseModel):
    free_recall: str = Field(default="", max_length=MAX_TEXT)
    free_recall_source: Source | None = None
    answers: list[AnswerIn] = []

    @field_validator("answers")
    @classmethod
    def one_answer_per_question(cls, answers: list[AnswerIn]) -> list[AnswerIn]:
        keys = [a.key for a in answers]
        if len(keys) != len(set(keys)):
            raise ValueError("each question can be answered only once")
        return answers


class InterviewOut(BaseModel):
    id: int
    case_id: int
    status: str
    free_recall: str
    free_recall_source: str | None
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
    iv.answers = [
        {"key": a.key, "prompt": PROMPTS[a.key], "answer": a.answer, "status": a.status, "source": a.source}
        for a in body.answers
    ]
    session.add(iv)
    session.commit()
    session.refresh(iv)
    return InterviewOut(**iv.model_dump())
