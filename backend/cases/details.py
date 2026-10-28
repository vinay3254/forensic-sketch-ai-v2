"""Facts about the person and the incident that are not part of the face.

Shown on the case sheet. Incident fields (approach, weapon, offence, requesting unit,
reference) are never sent to an image model."""

from pydantic import BaseModel, ConfigDict, Field

Text = Field(default=None, max_length=500)


class CaseDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # the person
    height: str | None = Text
    build: str | None = Text
    clothing: str | None = Text
    movement: str | None = Text
    voice: str | None = Text
    other_traits: str | None = Text
    # the incident
    approach: str | None = Text
    weapon: str | None = Text
    offence: str | None = Text
    requesting_unit: str | None = Text
    reference: str | None = Text

    def stored(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v and v.strip()}


# interview questions whose answers fill a detail field of the same name
INTERVIEW_FIELDS = ("height", "build", "clothing", "movement", "voice")


def prefill_from_interview(details: dict, answers: list[dict]) -> dict:
    """Fill empty person fields with the witness's words, verbatim. What the officer already
    typed stays; answers marked "Don't know" or left blank add nothing."""
    out = dict(details)
    for a in answers:
        if a["key"] in INTERVIEW_FIELDS and a["status"] != "unknown" and a["answer"].strip() and not out.get(a["key"]):
            out[a["key"]] = a["answer"]
    return out
