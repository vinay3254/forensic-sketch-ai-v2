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
