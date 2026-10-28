"""Draw the five body-type reference figures once and save them to backend/assets/body_types/.

Usage: AI_MOCK=0 uv run python -m scripts.make_body_types [key ...]
The PNGs are committed; rerun only to replace a figure.
"""

import io
import sys

from PIL import Image

from backend.ai.client import LiveAIClient
from backend.body.types import ASSETS, BODY_TYPES
from backend.config import get_settings
from backend.face.service import normalize_image

HEIGHT = 600
BUILDS = {
    "slim": "a slim, lean build with narrow shoulders and thin arms and legs",
    "athletic": "an athletic, muscular build with broad shoulders and a flat stomach",
    "overweight": "a slightly overweight build with a soft stomach",
    "heavy": "a heavy build with a large round stomach and thick arms and legs",
    "obese": "a very heavy, obese build with a very large stomach and wide hips",
}


def prompt(build: str) -> str:
    return (
        f"Hand-drawn pencil reference figure of an adult man with {build}. Plain short-sleeved t-shirt and "
        "knee-length shorts, simple shoes. Front view, standing straight, arms relaxed at the sides, the whole "
        "body from head to feet, the face left blank with no features. Soft pencil on plain white paper, black and "
        "white only, plain background."
    )


def main() -> None:
    settings = get_settings()
    ai = LiveAIClient(settings)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for key, label in BODY_TYPES:
        if len(sys.argv) > 1 and key not in sys.argv[1:]:
            continue
        img = Image.open(io.BytesIO(normalize_image(ai.generate_image(prompt(BUILDS[key])), settings.llm_image_size)))
        img = img.resize((round(img.width * HEIGHT / img.height), HEIGHT), Image.Resampling.LANCZOS)
        img.save(ASSETS / f"{key}.png", optimize=True)
        print(f"{label}: saved {ASSETS / f'{key}.png'}")


if __name__ == "__main__":
    main()
