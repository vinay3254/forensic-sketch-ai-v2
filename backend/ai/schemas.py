from typing import Literal

from pydantic import BaseModel

Region = Literal[
    "face_shape", "jaw", "eyes", "eyebrows", "nose", "mouth", "ears",
    "hair", "facial_hair", "appearance", "skin_tone", "marks", "age_range", "accessories",
]


class Attributes(BaseModel):
    gender: str | None = None
    age_range: str | None = None
    appearance: str | None = None  # ethnic / regional appearance, in the witness's words
    skin_tone: str | None = None
    face_shape: str | None = None
    jaw: str | None = None
    eyes: str | None = None
    eyebrows: str | None = None
    nose: str | None = None
    mouth: str | None = None
    ears: str | None = None
    hair: str | None = None
    facial_hair: str | None = None
    marks: str | None = None
    accessories: str | None = None
    notes: str | None = None


class Edit(BaseModel):
    region: Region
    change: str


class EditPlan(BaseModel):
    edits: list[Edit]
    reply: str
    needs_clarification: bool = False


class CoverageQuote(BaseModel):
    key: str
    quote: str


class Coverage(BaseModel):
    covered: list[CoverageQuote]


class Translation(BaseModel):
    english: str


class FigureEdit(BaseModel):
    changes: dict  # FigureParams fields to set (figure/params.py clamps and validates them)
    reply: str
