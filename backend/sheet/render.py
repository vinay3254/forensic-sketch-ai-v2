"""Draw the one-page case sheet: A4 landscape at 300 dpi, black on white, from stored data only."""

import textwrap
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 3508, 2480  # A4 landscape, 300 dpi
M = 100  # page margin
INK, GREY, LINE = 0, 90, 150

FACE_LABELS = {
    "gender": "Gender", "age_range": "Age", "appearance": "Ethnic appearance", "skin_tone": "Skin", "face_shape": "Face shape", "jaw": "Jaw",
    "eyes": "Eyes", "eyebrows": "Eyebrows", "nose": "Nose", "mouth": "Mouth", "ears": "Ears", "hair": "Hair",
    "facial_hair": "Facial hair", "marks": "Marks", "accessories": "Accessories", "notes": "Notes",
}
PERSON_LABELS = {
    "height": "Height", "build": "Build", "clothing": "Clothing", "movement": "Movement",
    "voice": "Voice and speech", "other_traits": "Other traits",
}
INCIDENT_LABELS = {"approach": "Approach", "weapon": "Weapon"}


@dataclass
class SheetData:
    case_number: str
    title: str
    details: dict
    sketch: Image.Image
    version_no: int
    attributes: dict
    uncertain: list[str]
    exported_by: str
    exported_at: str
    variants: list[tuple[str, Image.Image]] = field(default_factory=list)  # (label, image), oldest first
    body: Image.Image | None = None
    body_types: list[tuple[str, Image.Image]] = field(default_factory=list)  # (label, image)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def fit(img: Image.Image, w: int, h: int) -> Image.Image:
    return ImageOps.contain(img.convert("L"), (w, h), Image.Resampling.LANCZOS)


def paste_framed(page: Image.Image, img: Image.Image, x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    """Paste `img` scaled into the box, centred horizontally, framed; returns the frame."""
    im = fit(img, w, h)
    left = x + (w - im.width) // 2
    page.paste(im, (left, y))
    box = (left - 4, y - 4, left + im.width + 4, y + im.height + 4)
    ImageDraw.Draw(page).rectangle(box, outline=LINE, width=4)
    return box


def header_title(case_number: str, title: str) -> str:
    return textwrap.shorten(f"Case {case_number} · {title}", 70, placeholder="…")


def section(
    draw: ImageDraw.ImageDraw, x: int, y: int, width: int, title: str, rows: list[tuple[str, str]], max_y: int
) -> int:
    """Heading plus label/value rows with wrapped values; returns the y below it. Text that would
    pass `max_y` is cut with a pointer to the case file, so it never runs into the variants."""
    if not rows or y + 140 > max_y:
        return y
    draw.text((x, y), title.upper(), fill=INK, font=font(46))
    y += 62
    draw.line((x, y, x + width, y), fill=LINE, width=3)
    y += 18
    label_w, size = 330, 38
    chars = max(20, (width - label_w) // (size // 2 + 1))
    step = size + 10
    for label, value in rows:
        lines = textwrap.wrap(value, chars) or [""]
        if y + step * 2 > max_y:  # room for one more line plus the cut note
            draw.text((x, y), "… more in the case file", fill=GREY, font=font(size))
            return min(y + step, max_y)
        draw.text((x, y), label, fill=GREY, font=font(size))
        room = (max_y - y) // step - 1
        if len(lines) > room:
            lines = lines[: room - 1] + ["… more in the case file"]
        for line in lines:
            draw.text((x + label_w, y), line, fill=INK, font=font(size))
            y += step
        y += 8
    return min(y + 30, max_y)


def render_sheet(d: SheetData) -> Image.Image:
    page = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(page)

    # header
    draw.text((M, M), "COMPOSITE SKETCH", fill=INK, font=font(96))
    draw.text((M, M + 120), header_title(d.case_number, d.title), fill=INK, font=font(52))
    meta = [
        (label, d.details[key])
        for key, label in [("requesting_unit", "Requesting unit"), ("reference", "Reference"), ("offence", "Offence")]
        if d.details.get(key)
    ] + [("Date", d.exported_at[:10])]
    for i, (label, value) in enumerate(meta):
        draw.text((W - M - 1300, M + 10 + i * 52), f"{label}: {textwrap.shorten(value, 52)}", fill=INK, font=font(40))
    draw.line((M, M + 230, W - M, M + 230), fill=INK, width=6)

    top = M + 270
    bottom = H - M - 90 - (460 if d.variants else 0)

    # main sketch
    frame = paste_framed(page, d.sketch, M, top, 1000, bottom - top - 60)
    draw.text((frame[0], frame[3] + 12), f"Sketch, version {d.version_no}", fill=GREY, font=font(36))

    # text sections
    x, width = M + 1080, 1260
    face = [
        (label, f"{d.attributes[k]} (uncertain)" if k in d.uncertain else d.attributes[k])
        for k, label in FACE_LABELS.items()
        if d.attributes.get(k)
    ]
    person = [(lbl, d.details[k]) for k, lbl in PERSON_LABELS.items() if d.details.get(k)]
    incident = [(lbl, d.details[k]) for k, lbl in INCIDENT_LABELS.items() if d.details.get(k)]
    y = section(draw, x, top, width, "Face", face, bottom)
    y = section(draw, x, y, width, "Person", person, bottom)
    section(draw, x, y, width, "Incident", incident, bottom)

    # full-body figure with the witness's height beside a bar
    rx, rw = M + 2420, W - 2 * M - 2420
    chart_h = 420 if d.body_types else 0
    if d.body:
        fig_h = bottom - top - chart_h - 120
        box = paste_framed(page, d.body, rx, top, rw - 220, fig_h)
        if d.details.get("height"):
            bx = box[2] + 50
            draw.line((bx, box[1], bx, box[3]), fill=INK, width=4)
            for yy in (box[1], box[3]):
                draw.line((bx - 20, yy, bx + 20, yy), fill=INK, width=4)
            for i, line in enumerate(textwrap.wrap(d.details["height"], 10)[:4]):
                draw.text((bx + 30, (box[1] + box[3]) // 2 - 40 + i * 44), line, fill=INK, font=font(38))

    # body-type chart, the witness's build highlighted
    if d.body_types:
        cy = bottom - chart_h
        draw.text((rx, cy), "BUILD REFERENCE", fill=INK, font=font(40))
        cell = rw // len(d.body_types)
        build = (d.details.get("build") or "").strip().lower()
        for i, (label, img) in enumerate(d.body_types):
            cx = rx + i * cell
            box = paste_framed(page, img, cx + 10, cy + 60, cell - 20, chart_h - 120)
            if label.lower() == build:
                draw.rectangle((box[0] - 8, box[1] - 8, box[2] + 8, box[3] + 8), outline=INK, width=10)
            draw.text(((box[0] + box[2]) // 2, box[3] + 14), label, fill=INK, font=font(30), anchor="ma")

    # numbered disguise variants
    if d.variants:
        vy = bottom + 10
        draw.text((M, vy), "VARIANTS", fill=INK, font=font(40))
        n = len(d.variants)
        cell = (W - 2 * M) // max(n, 10)
        for i, (label, img) in enumerate(d.variants):
            cx = M + i * cell
            paste_framed(page, img, cx + 10, vy + 60, cell - 20, 300)
            draw.text((cx + 10, vy + 380), f"{i + 1}. {label}", fill=INK, font=font(32))

    # footer
    draw.line((M, H - M - 70, W - M, H - M - 70), fill=LINE, width=3)
    draw.text(
        (M, H - M - 50),
        f"Version {d.version_no} · Exported {d.exported_at} by {d.exported_by} · "
        "Composite sketch: an investigative aid, not a photograph.",
        fill=GREY,
        font=font(36),
    )
    return page
