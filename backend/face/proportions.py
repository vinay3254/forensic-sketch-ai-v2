"""Proportion sliders: reshape the sketch locally, like Photoshop's Liquify, with no AI call.

Words lose a face's proportions (eye size, face length, nose length), and those are what
make it recognisable. The witness drags sliders until it looks right instead. Landmarks
come from the face parser's class map; each slider is a smooth local scale or shift around
them, applied as one backward-mapped displacement field so the drawing stays intact."""

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from backend.face.regions import BROWS, FACE_CLASSES, L_LIP, MOUTH, NOSE, PARSE_SIZE, SKIN, U_LIP

Slider = Field(default=0.0, ge=-1, le=1)
LABELS = {
    "eye_size": "eye size", "eye_spacing": "eye spacing", "nose_length": "nose length", "nose_width": "nose width",
    "mouth_width": "mouth width", "face_length": "face length", "jaw_width": "jaw width",
}


class Adjust(BaseModel):
    """Each slider runs from -1 to 1; 0 leaves that part as drawn."""

    model_config = ConfigDict(extra="forbid")

    eye_size: float = Slider
    eye_spacing: float = Slider
    nose_length: float = Slider
    nose_width: float = Slider
    mouth_width: float = Slider
    face_length: float = Slider
    jaw_width: float = Slider

    def is_zero(self) -> bool:
        return not any(self.model_dump().values())

    def describe(self) -> str:
        return ", ".join(f"{LABELS[k]} {v * 100:+.0f}%" for k, v in self.model_dump().items() if v)


@dataclass
class Landmarks:
    """Points in parser coordinates (PARSE_SIZE square). Boxes are (left, top, right, bottom), inclusive."""

    eyes: tuple[tuple[float, float], tuple[float, float]]  # image-left eye first
    eye_r: float
    nose: tuple[int, int, int, int]
    mouth: tuple[float, float, float, float]
    chin: int
    face_left: int
    face_right: int


def _box(pts: np.ndarray) -> tuple[int, int, int, int]:
    return int(pts[:, 1].min()), int(pts[:, 0].min()), int(pts[:, 1].max()), int(pts[:, 0].max())


def landmarks(m: np.ndarray) -> Landmarks | None:
    """None when the map does not show a face with both brows and a nose."""
    face = np.argwhere(np.isin(m, (*FACE_CLASSES, MOUTH, U_LIP, L_LIP)))
    skin, brows, nose = np.argwhere(m == SKIN), np.argwhere(np.isin(m, BROWS)), np.argwhere(m == NOSE)
    if not len(skin) or not len(brows) or not len(nose):
        return None
    face_left, _, face_right, chin = _box(face)
    cx = (face_left + face_right) / 2
    sides = [brows[brows[:, 1] < cx], brows[brows[:, 1] >= cx]]
    if not all(len(s) for s in sides):
        return None
    nose_box = _box(nose)
    brow_bottom = brows[:, 0].max()
    eye_y = brow_bottom + 0.45 * (nose_box[1] - brow_bottom)  # eyes sit a little above halfway to the nose
    eyes = tuple((float(s[:, 1].mean()), float(eye_y)) for s in sides)
    eye_r = float(np.mean([(s[:, 1].max() - s[:, 1].min()) / 2 for s in sides]))
    lips = np.argwhere(np.isin(m, (MOUTH, U_LIP, L_LIP)))
    if len(lips):
        mouth = tuple(float(v) for v in _box(lips))
    else:  # the parser often misses pencil lips: estimate from the nose and chin
        below = chin - nose_box[3]
        mid, half = (nose_box[0] + nose_box[2]) / 2, (nose_box[2] - nose_box[0]) * 0.75
        y = nose_box[3] + 0.3 * below
        mouth = (mid - half, y - 0.06 * below, mid + half, y + 0.06 * below)
    return Landmarks(eyes, eye_r, nose_box, mouth, int(chin), int(face_left), int(face_right))


def _falloff(u: np.ndarray) -> np.ndarray:
    """1 at the centre, easing to 0 at u = 1 (u is squared normalised distance)."""
    return np.clip(1 - u, 0, 1) ** 2


def _sample(img: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    h, w = img.shape
    x, y = np.clip(x, 0, w - 1), np.clip(y, 0, h - 1)
    x0, y0 = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = x - x0, y - y0
    top = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    bottom = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return top * (1 - fy) + bottom * fy


def warp(data: bytes, lm: Landmarks, adj: Adjust, width: int | None = None) -> bytes:
    """The sketch with `adj` applied, as PNG; `width` scales it down first (for fast previews)."""
    img = Image.open(io.BytesIO(data)).convert("L")
    if width and img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.BILINEAR)
    src = np.asarray(img, np.float32)
    h, w = src.shape
    kx, ky = w / PARSE_SIZE, h / PARSE_SIZE
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = np.zeros_like(X), np.zeros_like(Y)

    def scale(cx, cy, rx, ry, sx, sy):
        nonlocal dx, dy
        wgt = _falloff(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
        dx += (X - cx) * (1 / (1 + (sx - 1) * wgt) - 1)
        dy += (Y - cy) * (1 / (1 + (sy - 1) * wgt) - 1)

    def shift(cx, cy, rx, ry, tx, ty):
        nonlocal dx, dy
        wgt = _falloff(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
        dx -= tx * wgt
        dy -= ty * wgt

    eyes = [(ex * kx, ey * ky) for ex, ey in lm.eyes]
    er = lm.eye_r * kx
    nl, nt, nr, nb = lm.nose[0] * kx, lm.nose[1] * ky, lm.nose[2] * kx, lm.nose[3] * ky
    nose_w, nose_h, nose_cx = nr - nl + 1, nb - nt + 1, (nl + nr) / 2
    ml, mt, mr, mb = lm.mouth[0] * kx, lm.mouth[1] * ky, lm.mouth[2] * kx, lm.mouth[3] * ky
    chin, face_cx = lm.chin * ky, (lm.face_left + lm.face_right) / 2 * kx
    face_w = (lm.face_right - lm.face_left + 1) * kx
    eye_y = eyes[0][1]
    length = chin - eye_y

    if adj.eye_size:
        s = 1 + 0.25 * adj.eye_size
        for ex, ey in eyes:
            scale(ex, ey, er * 1.3, er * 0.9, s, s)
    if adj.eye_spacing:
        t = 0.08 * face_w * adj.eye_spacing
        for (ex, ey), sign in zip(eyes, (-1, 1)):
            shift(ex, ey, er * 1.4, er, sign * t, 0)
    if adj.nose_width:
        scale(nose_cx, (nt + nb) / 2, nose_w * 0.9, nose_h * 0.8, 1 + 0.3 * adj.nose_width, 1)
    if adj.nose_length:
        shift(nose_cx, nb, nose_w * 0.9, nose_h * 0.6, 0, 0.25 * nose_h * adj.nose_length)
    if adj.mouth_width:
        scale((ml + mr) / 2, (mt + mb) / 2, (mr - ml) * 0.9, max((mb - mt) * 2, nose_h * 0.5),
              1 + 0.25 * adj.mouth_width, 1)
    if adj.face_length:
        # the lower face stretches from the eye line down; below the chin the shift fades out
        t, fade = 0.12 * length * adj.face_length, 0.6 * length
        profile = np.where(Y < eye_y, 0, np.where(Y <= chin, (Y - eye_y) / length, np.clip(1 - (Y - chin) / fade, 0, 1)))
        dy -= t * profile * _falloff(((X - face_cx) / (face_w * 0.8)) ** 2)
    if adj.jaw_width:
        # widest effect along the jaw, none above the nose, fading out below the chin
        top, mouth_y = (nt + nb) / 2, (mt + mb) / 2
        wy = np.where(Y < top, 0, np.where(Y < mouth_y, (Y - top) / max(mouth_y - top, 1),
                      np.clip(1 - (Y - chin) / (0.4 * length), 0, 1)))
        wgt = wy * _falloff(((X - face_cx) / (face_w * 0.9)) ** 2)
        dx += (X - face_cx) * (1 / (1 + 0.2 * adj.jaw_width * wgt) - 1)

    out = Image.fromarray(np.clip(_sample(src, X + dx, Y + dy), 0, 255).astype(np.uint8), "L")
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()
