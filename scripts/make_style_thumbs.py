"""Draw the style library thumbnails once and save them to backend/assets/styles/<key>.png.

Usage: AI_MOCK=0 uv run python -m scripts.make_style_thumbs [key ...]   (existing files are skipped)
"""

import io
import sys

from PIL import Image

from backend.ai.client import LiveAIClient
from backend.config import get_settings
from backend.errors import AppError
from backend.styles.catalog import CATEGORIES

OUT = __import__("pathlib").Path(__file__).resolve().parent.parent / "backend" / "assets" / "styles"
SIZE = 360


def main() -> None:
    settings = get_settings()
    ai = LiveAIClient(settings)
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = set(sys.argv[1:])
    for c in CATEGORIES:
        for s in c.styles:
            path = OUT / f"{s.key}.png"
            if (wanted and s.key not in wanted) or (not wanted and path.exists()):
                continue
            prompt = (
                f"Quick hand-drawn {c.thumb.format(change=s.change)}. Soft graphite pencil on plain white paper, "
                "loose outlines and light hatching, the item drawn clearly and centred, no face details, "
                "plain white background, black and white only, no text."
            )
            try:
                raw = ai.generate_image(prompt)
            except AppError as e:
                print(f"{s.key}: failed ({e.code})", flush=True)
                continue
            img = Image.open(io.BytesIO(raw)).convert("L")
            side = min(img.size)
            img = img.crop(((img.width - side) // 2, (img.height - side) // 2, (img.width + side) // 2, (img.height + side) // 2))
            img.resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(path, optimize=True)
            print(f"{s.key}: saved", flush=True)


if __name__ == "__main__":
    main()
