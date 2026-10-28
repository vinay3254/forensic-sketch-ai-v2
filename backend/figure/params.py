"""The numbers the Blender worker builds a figure from, and how case facts become them."""

import re
from typing import Literal

from pydantic import BaseModel, Field

Top = Literal["none", "tshirt", "shirt", "hoodie", "jacket", "kurta"]
Bottom = Literal["none", "trousers", "jeans", "shorts", "skirt"]
Headwear = Literal["none", "cap"]
TOPS, BOTTOMS, HEADWEAR = Top.__args__, Bottom.__args__, Headwear.__args__
LIMITS = {"height_cm": (120, 220), "build": (0, 1), "muscle": (0, 1), "gender": (0, 1), "age": (10, 100)}


class FigureParams(BaseModel):
    height_cm: float = Field(172, ge=120, le=220)
    build: float = Field(0.35, ge=0, le=1)  # 0 slim .. 1 obese
    muscle: float = Field(0.4, ge=0, le=1)
    gender: float = Field(0.0, ge=0, le=1)  # 0 male .. 1 female
    age: float = Field(35, ge=10, le=100)
    top: Top = "tshirt"
    bottom: Bottom = "trousers"
    headwear: Headwear = "none"


def apply_changes(p: FigureParams, changes: dict) -> FigureParams:
    """Merge model-proposed changes: numbers are clamped, unknown clothing is ignored."""
    data = p.model_dump()
    for key, value in changes.items():
        if key in LIMITS:
            try:
                lo, hi = LIMITS[key]
                data[key] = max(lo, min(hi, float(value)))
            except (TypeError, ValueError):
                continue
        elif key == "top" and value in TOPS or key == "bottom" and value in BOTTOMS or key == "headwear" and value in HEADWEAR:
            data[key] = value
    return FigureParams(**data)


def parse_height_cm(text: str | None) -> float | None:
    if not text:
        return None
    t = text.lower()
    if m := re.search(r"(\d)\s*(?:'|ft|feet|foot)\s*(\d{1,2})?", t):
        return int(m.group(1)) * 30.48 + int(m.group(2) or 0) * 2.54
    if m := re.search(r"(\d{3})\s*(?:cm)?", t):
        return float(m.group(1))
    if m := re.search(r"(\d\.\d{1,2})\s*m", t):
        return float(m.group(1)) * 100
    return None


BUILDS = [("obese", 0.95), ("heavy", 0.75), ("fat", 0.8), ("overweight", 0.55), ("chubby", 0.55), ("stocky", 0.6),
          ("athletic", 0.3), ("muscular", 0.3), ("average", 0.35), ("medium", 0.35), ("slim", 0.1), ("thin", 0.08), ("lean", 0.15)]
DECADES = {"teens": 16, "twenties": 25, "thirties": 35, "forties": 45, "fifties": 55, "sixties": 65, "seventies": 75}


def parse_age(text: str | None) -> float | None:
    if not text:
        return None
    t = text.lower()
    if nums := [int(n) for n in re.findall(r"\b(\d{2})\b", t)]:
        return sum(nums) / len(nums) + (5 if re.search(r"\d0s\b", t) else 0)
    for word, mid in DECADES.items():
        if word in t:
            return mid - 3 if "early" in t else mid + 3 if "late" in t else mid
    return None


def clothing_from(text: str | None) -> dict:
    t = (text or "").lower()
    out = {}
    for word, top in [("kurta", "kurta"), ("hoodie", "hoodie"), ("sweatshirt", "hoodie"), ("jacket", "jacket"),
                      ("blazer", "jacket"), ("t-shirt", "tshirt"), ("tshirt", "tshirt"), ("tee", "tshirt"), ("shirt", "shirt")]:
        if word in t:
            out["top"] = top
            break
    for word, bottom in [("jeans", "jeans"), ("shorts", "shorts"), ("skirt", "skirt"), ("trousers", "trousers"), ("pants", "trousers")]:
        if word in t:
            out["bottom"] = bottom
            break
    if re.search(r"\b(cap|hat)\b", t):
        out["headwear"] = "cap"
    return out


def defaults_for(details: dict, attributes: dict) -> FigureParams:
    """A first figure from what the case already says; anything unknown stays at the default."""
    changes: dict = {}
    if (h := parse_height_cm(details.get("height"))) is not None:
        changes["height_cm"] = h
    build = (details.get("build") or "").lower()
    for word, value in BUILDS:
        if word in build:
            changes["build"] = value
            if word in ("athletic", "muscular"):
                changes["muscle"] = 0.85
            break
    gender = (attributes.get("gender") or "").lower()
    if re.search(r"\b(female|woman|girl|lady)\b", gender):
        changes["gender"] = 1.0
    if (age := parse_age(attributes.get("age_range"))) is not None:
        changes["age"] = age
    changes.update(clothing_from(details.get("clothing")))
    return apply_changes(FigureParams(), changes)
