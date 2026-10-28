from PIL import Image, ImageDraw, ImageFont, ImageOps


def upscale(img: Image.Image, long_side: int = 2048) -> Image.Image:
    scale = long_side / max(img.size)
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)


def to_sketch(img: Image.Image) -> Image.Image:
    """Faces are generated as pencil sketches, so only deepen the contrast for printing.
    (An edge filter here would wash the graphite shading out to white.)"""
    return ImageOps.autocontrast(img.convert("L"), cutoff=1)


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
