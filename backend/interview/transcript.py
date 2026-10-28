import hashlib
import json

from backend.interview.questions import EXTRAS, FEATURES

ORDER = {q["key"]: i for i, q in enumerate(FEATURES + EXTRAS)}


def in_question_order(answers: list[dict]) -> list[dict]:
    return sorted(answers, key=lambda a: ORDER[a["key"]])


def canonical_transcript(iv: dict) -> str:
    """The exact text the confirmation hash covers: the witness's words and how sure they were."""
    return json.dumps(
        {
            "interview_id": iv["id"],
            "case_id": iv["case_id"],
            "free_recall": iv["free_recall"],
            "free_recall_source": iv["free_recall_source"],
            "answers": iv["answers"],
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def transcript_hash(iv: dict) -> str:
    return hashlib.sha256(canonical_transcript(iv).encode()).hexdigest()


def has_content(iv: dict) -> bool:
    return bool(iv["free_recall"].strip()) or any(a["answer"].strip() for a in iv["answers"])


# which sketch attributes each interview question speaks to
FIELDS_FOR = {
    "age_gender": ("gender", "age_range"),
    "skin_tone": ("skin_tone",),
    "face_shape": ("face_shape",),
    "eyes": ("eyes",),
    "eyebrows": ("eyebrows",),
    "nose": ("nose",),
    "mouth": ("mouth",),
    "ears": ("ears",),
    "jaw_chin": ("jaw",),
    "facial_hair": ("facial_hair",),
    "hairstyle": ("hair",),
    "glasses_accessories": ("accessories",),
    "distinguishing_features": ("marks",),
}

LABELS = {q["key"]: q["label"] for q in FEATURES + EXTRAS}


def render_description(iv: dict) -> str:
    """What the attribute extractor reads: the witness's words verbatim, labelled with how sure they were.
    Questions that were not asked are left out, so the free account can still speak to them."""
    lines = [
        "Witness interview transcript. Quoted text is the witness's own words.",
        "A feature marked 'not remembered' must be null. Never invent details.",
    ]
    if iv["free_recall"].strip():
        lines.append(f'Free account: "{iv["free_recall"]}"')
    for a in iv["answers"]:
        label = LABELS[a["key"]]
        if a["status"] == "unknown":
            lines.append(f"{label}: not remembered")
        elif a["answer"].strip():
            lines.append(f'{label} ({a["status"] or "not rated"}): "{a["answer"]}"')
    return "\n".join(lines)


def fields_with_status(iv: dict, status: str) -> list[str]:
    return sorted({f for a in iv["answers"] if a["status"] == status for f in FIELDS_FOR[a["key"]]})
