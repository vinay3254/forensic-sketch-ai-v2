from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, UniqueConstraint
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Store naive UTC (SQLite has no timezone support); always hand back aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


def ts_field() -> datetime:
    return Field(default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False))


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str  # "officer" | "admin"
    created_at: datetime = ts_field()


class RevokedToken(SQLModel, table=True):
    """Sessions ended by logout; checked on every request until the token would have expired anyway."""

    jti: str = Field(primary_key=True)
    expires_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))


class Case(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_number: str = Field(unique=True)
    title: str
    created_by: int = Field(foreign_key="user.id")
    status: str = "open"
    created_at: datetime = ts_field()


class FaceVersion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("case_id", "version_no"),)

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    parent_id: int | None = Field(default=None, foreign_key="faceversion.id")
    version_no: int
    kind: str  # "generate" | "refine" | "revert"
    instruction: str
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    prompt: str
    image_path: str
    photo_path: str | None = None  # realistic photo made from this sketch, on request
    interview_id: int | None = Field(default=None, foreign_key="interview.id")  # set when made from an interview
    # attribute names the witness was unsure about; carried through refines and reverts
    uncertain: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = ts_field()


class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    role: str  # "user" | "assistant"
    content: str
    version_id: int | None = Field(default=None, foreign_key="faceversion.id")
    created_at: datetime = ts_field()


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = ts_field()
    user_id: int | None = None
    username: str | None = None
    role: str | None = None
    action: str = Field(index=True)
    case_id: int | None = Field(default=None, index=True)
    version_id: int | None = None
    ip: str | None = None
    user_agent: str | None = None
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    prev_hash: str
    hash: str


class Interview(SQLModel, table=True):
    """Officer-led witness interview. Answers are stored exactly as entered; once
    confirmed the transcript is locked and its hash goes to the audit log."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    status: str = "draft"  # "draft" | "confirmed"
    free_recall: str = ""
    free_recall_source: str | None = None  # "typed" | "speech" | "mixed"
    # [{key, prompt, answer, status, source}]; prompt is copied from the fixed bank
    answers: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = ts_field()
    confirmed_by: int | None = Field(default=None, foreign_key="user.id")
    confirmed_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime(), nullable=True))
    transcript_hash: str | None = None
