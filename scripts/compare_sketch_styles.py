"""Generate one live sketch and save it with both finishes, to compare SKETCH_FINISH options.

Usage: AI_MOCK=0 uv run python -m scripts.compare_sketch_styles ["witness description"] [out_dir]
Writes sketch_clean.png, sketch_scanned.png and sketch_compare.png (side by side) to out_dir (default: .).
"""

import io
import sys
from pathlib import Path

from PIL import Image

from backend.ai.client import LiveAIClient
from backend.ai.prompts import build_image_prompt
from backend.config import get_settings
from backend.face.service import normalize_image, scanned_finish

DEFAULT_DESCRIPTION = (
    "He was young, maybe early twenties. Curly hair, kind of messy. I remember his eyes were really narrow, "
    "like squinting. There was a mark near his eyebrow, I think."
)


def main() -> None:
    description = (sys.argv[1] if len(sys.argv) > 1 else "") or DEFAULT_DESCRIPTION
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    out.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    ai = LiveAIClient(settings)
    prompt = build_image_prompt(ai.extract_attributes(description))
    print(prompt)
    clean = normalize_image(ai.generate_image(prompt), settings.llm_image_size)
    scanned = scanned_finish(clean)
    (out / "sketch_clean.png").write_bytes(clean)
    (out / "sketch_scanned.png").write_bytes(scanned)
    a, b = Image.open(io.BytesIO(clean)), Image.open(io.BytesIO(scanned))
    pair = Image.new("L", (a.width * 2 + 20, a.height), 255)
    pair.paste(a, (0, 0))
    pair.paste(b, (a.width + 20, 0))
    pair.save(out / "sketch_compare.png")
    print(f"Saved sketch_clean.png, sketch_scanned.png, sketch_compare.png in {out}")


if __name__ == "__main__":
    main()
