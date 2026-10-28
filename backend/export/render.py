import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def upscale(img: Image.Image, long_side: int = 2048) -> Image.Image:
    scale = long_side / max(img.size)
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)


def to_sketch(img: Image.Image) -> Image.Image:
    gray = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(255 - gray, (21, 21), 0)
    sketch = cv2.divide(gray, 255 - blurred, scale=256)
    sketch = cv2.convertScaleAbs(sketch, alpha=1.15, beta=0)
    return Image.fromarray(sketch, mode="L")


def stamp_footer(img: Image.Image, lines: list[str]) -> Image.Image:
    strip = max(60, int(img.height * 0.04))
    white = 255 if img.mode == "L" else (255, 255, 255)
    black = 0 if img.mode == "L" else (0, 0, 0)
    out = Image.new(img.mode, (img.width, img.height + strip), white)
    out.paste(img, (0, 0))
    font_size = max(14, strip // (len(lines) + 1))
    font = ImageFont.load_default(size=font_size)
    draw = ImageDraw.Draw(out)
    for i, line in enumerate(lines):
        draw.text((20, img.height + 8 + i * (font_size + 4)), line, fill=black, font=font)
    return out
