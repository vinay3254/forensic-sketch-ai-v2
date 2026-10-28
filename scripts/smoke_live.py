"""Call the live LLM service once per AI operation and report timings.

Usage: AI_MOCK=0 uv run python scripts/smoke_live.py
Needs LLM_BASE_URL, LLM_API_KEY, LLM_CHAT_MODEL and LLM_IMAGE_MODEL in .env.
"""

import time
from pathlib import Path

from backend.ai.client import LiveAIClient
from backend.ai.prompts import apply_edits, build_edit_prompt, build_image_prompt
from backend.config import get_settings
from backend.seed import DEMO_DESCRIPTION, DEMO_REFINEMENT


def timed(label, fn, *args):
    start = time.perf_counter()
    result = fn(*args)
    print(f"{label:<20} {time.perf_counter() - start:6.1f} s")
    return result


def main() -> None:
    ai = LiveAIClient(get_settings())
    attrs = timed("extract_attributes", ai.extract_attributes, DEMO_DESCRIPTION)
    print(f"  {attrs.model_dump(exclude_none=True)}")
    v1 = timed("generate_image", ai.generate_image, build_image_prompt(attrs))
    Path("smoke_v1.png").write_bytes(v1)
    plan = timed("parse_edit", ai.parse_edit, DEMO_REFINEMENT, attrs)
    print(f"  {plan.model_dump()}")
    if not plan.edits:
        print("No edits returned; skipping edit_image.")
        return
    v2 = timed("edit_image", ai.edit_image, v1, build_edit_prompt(plan.edits))
    Path("smoke_v2.png").write_bytes(v2)
    print(f"  attributes after edit: {apply_edits(attrs, plan.edits).model_dump(exclude_none=True)}")
    print("Saved smoke_v1.png and smoke_v2.png")


if __name__ == "__main__":
    main()
