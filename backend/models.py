from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, UniqueConstraint, Index, text
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
    # person and incident facts for the case sheet (backend/cases/details.py)
    details: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    figure: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))  # Blender figure settings
    created_at: datetime = ts_field()


class FaceVersion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("case_id", "version_no"),)

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    parent_id: int | None = Field(default=None, foreign_key="faceversion.id")
    version_no: int
    kind: str  # "generate" | "refine" | "revert" | "adjust" (proportion sliders) | ...
    instruction: str
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    prompt: str
    image_path: str
    photo_path: str | None = None  # realistic photo made from this sketch, on request
    interview_id: int | None = Field(default=None, foreign_key="interview.id")  # set when made from an interview
    # attribute names the witness was unsure about; carried through refines and reverts
    uncertain: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    localized: bool | None = None  # refine only: old sketch pasted back outside the edited regions
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = ts_field()


class Variant(SQLModel, table=True):
    """A disguise variant (cap, glasses, beard...) of one sketch version. Not part of the version line."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    version_id: int = Field(foreign_key="faceversion.id")
    kind: str
    image_path: str
    prompt: str
    localized: bool = False
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = ts_field()


class BodyFigure(SQLModel, table=True):
    """Full-length pencil figure from the case's build and clothing; the newest one is used."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    image_path: str
    prompt: str
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = ts_field()


class BodyModel(SQLModel, table=True):
    """Colored reconstruction of one saved full-body source image."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    body_id: int = Field(foreign_key="bodyfigure.id")
    mesh_path: str
    height_cm: float
    engine: str = "TripoSR"
    blend_path: str | None = None
    script_path: str | None = None
    summary: str | None = None
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = ts_field()


class BlenderJob(SQLModel, table=True):
    __table_args__ = (Index('unique_active_blender_case', 'case_id', unique=True,
                           sqlite_where=text("status IN ('queued','drafting','building','opening')"),
                           postgresql_where=text("status IN ('queued','drafting','building','opening')")),)
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    body_id: int = Field(foreign_key="bodyfigure.id")
    prompt: str
    status: str = "queued"
    worker_pid: int
    worker_token: str | None = None
    model_id: int | None = Field(default=None, foreign_key="bodymodel.id")
    error: str | None = None
    desktop_opened: bool = False
    desktop_error: str | None = None
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = ts_field()


class Head3D(SQLModel, table=True):
    """Approximate 3D head (GLB) made from a version's realistic photo by the head3d worker."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    version_id: int = Field(foreign_key="faceversion.id")
    mesh_path: str
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
    free_recall_lang: str | None = None  # set only when the witness spoke another language (backend/translate.py)
    free_recall_english: str | None = None  # its English translation, which the sketch is made from
    # [{key, prompt, answer, status, source[, lang, english]}]; prompt is copied from the fixed bank
    answers: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = ts_field()
    confirmed_by: int | None = Field(default=None, foreign_key="user.id")
    confirmed_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime(), nullable=True))
    transcript_hash: str | None = None


class RecordPerson(SQLModel, table=True):
    """Demo criminal-records database: a fictional person with a synthetic face (FLUXSynID).
    Nothing here describes a real person; see backend/records/seed.py."""

    id: int | None = Field(default=None, primary_key=True)
    record_no: str = Field(unique=True)
    name: str = Field(index=True)
    alias: str | None = None
    gender: str  # "male" | "female"
    age: int
    area: str
    height_cm: int
    build: str
    marks: str | None = None
    photo_path: str  # relative to storage_dir: the ID-style front photo
    live_photo_path: str | None = None  # a second photo of the same synthetic person (for matching tests)
    source: str  # e.g. "FLUXSynID 00000bb0d1b9_f"


class RecordCharge(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="recordperson.id", index=True)
    fir_no: str
    police_station: str
    date: str  # ISO date of the FIR
    section: str  # BNS section, e.g. "303(2)"
    offence: str
    status: str  # "under_investigation" | "charge_sheeted" | "convicted" | "acquitted"
