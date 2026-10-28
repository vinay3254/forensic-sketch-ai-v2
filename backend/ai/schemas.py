from typing import Literal

from pydantic import BaseModel

Region = Literal[
    "face_shape", "jaw", "eyes", "eyebrows", "nose", "mouth", "ears",
    "hair", "facial_hair", "skin_tone", "marks", "age_range", "accessories",
]


class Attributes(BaseModel):
    gender: str | None = None
    age_range: str | None = None
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
