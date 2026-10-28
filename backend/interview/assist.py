"""Option B: show which features the witness's free account already covers.

The AI only points at the witness's own words. Any quote that is not an exact
substring of the free account is dropped here, so nothing reworded reaches the officer."""

from backend.ai.client import AIClient
from backend.ai.schemas import Coverage
from backend.interview.questions import EXTRAS, FEATURES

LABELS = {q["key"]: q["label"] for q in FEATURES + EXTRAS}


def verbatim_coverage(free_recall: str, coverage: Coverage) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for c in coverage.covered:
        if c.key in LABELS and c.quote.strip() and c.quote in free_recall and c.quote not in found.get(c.key, []):
            found.setdefault(c.key, []).append(c.quote)
    return {k: found[k] for k in LABELS if k in found}  # question order


def find_coverage(ai: AIClient, free_recall: str) -> dict[str, list[str]]:
    return verbatim_coverage(free_recall, ai.find_coverage(free_recall, LABELS))
