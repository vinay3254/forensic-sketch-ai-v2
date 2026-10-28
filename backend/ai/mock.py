import io
import re
import textwrap

from PIL import Image, ImageDraw

from backend.ai.schemas import Attributes, Edit, EditPlan

_EDIT_KEYWORDS = [
    (r"\bjaw", "jaw"),
    (r"\beye(s)?\b", "eyes"),
    (r"\beyebrow", "eyebrows"),
    (r"\bnose\b", "nose"),
    (r"\b(lip|lips|mouth)\b", "mouth"),
    (r"\bhair\b", "hair"),
    (r"\b(beard|moustache|mustache|stubble)\b", "facial_hair"),
    (r"\bscar\b", "marks"),
]


def _word(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.I) is not None


class MockAIClient:
    """Deterministic stand-in for the LLM service: tests, offline demos, frontend work."""

    def extract_attributes(self, text: str) -> Attributes:
        a = Attributes()
        if _word(r"\b(female|woman|girl|lady)\b", text):
            a.gender = "female"
        elif _word(r"\b(male|man|boy|guy)\b", text):
            a.gender = "male"
        if m := re.search(r"\b(\d{2})\s*(s\b|years)", text, re.I):
            a.age_range = f"{m.group(1)}s"
        if m := re.search(r"\b(beard|moustache|mustache|stubble)\b", text, re.I):
            a.facial_hair = m.group(1).lower()
        if m := re.search(r"[^,.;]*\bscar\b[^,.;]*", text, re.I):
            a.marks = m.group(0).strip()
        return a

    def parse_edit(self, message: str, current: Attributes) -> EditPlan:
        edits = [Edit(region=region, change=message.strip()) for pat, region in _EDIT_KEYWORDS if _word(pat, message)]
        if not edits:
            return EditPlan(edits=[], reply="Which feature should change — eyes, nose, jaw, mouth or hair?",
                            needs_clarification=True)
        names = ", ".join(e.region.replace("_", " ") for e in edits)
        return EditPlan(edits=edits, reply=f"Updated the {names}.")

    def _placeholder(self, prompt: str) -> bytes:
        img = Image.new("RGB", (1024, 1536), (128, 128, 128))
        d = ImageDraw.Draw(img)
        d.text((40, 40), "MOCK PORTRAIT", fill=(255, 255, 255))
        for i, line in enumerate(textwrap.wrap(prompt[:80], 40)):
            d.text((40, 80 + i * 20), line, fill=(230, 230, 230))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def generate_image(self, prompt: str) -> bytes:
        return self._placeholder(prompt)

    def edit_image(self, image: bytes, prompt: str) -> bytes:
        return self._placeholder(prompt)
