"""Keep an AI edit inside the regions the witness asked about.

Image edits redraw the whole sketch, so details the witness already confirmed drift.
A face-parsing model (BiSeNet, CelebAMask-HQ classes) finds the edited regions in the
old and new sketch; the new pixels are kept there and the old ones pasted back elsewhere."""

import io
import logging
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image, ImageFilter

log = logging.getLogger(__name__)

PARSE_SIZE = 512
SKIN, L_BROW, R_BROW, GLASSES, L_EAR, R_EAR, EARRING, NOSE, MOUTH, U_LIP, L_LIP, CLOTH, HAIR, HAT = (
    1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 18,
)
BROWS = (L_BROW, R_BROW)
# edit regions without an entry here (jaw, face_shape, marks, ...) change the whole face
REGION_CLASSES = {
    "nose": (NOSE,),
    "mouth": (MOUTH, U_LIP, L_LIP),
    "eyebrows": BROWS,
    "ears": (L_EAR, R_EAR, EARRING),
    "hair": (HAIR, HAT),
    "accessories": (GLASSES,),
    "clothing": (CLOTH,),
    "eyes": (),  # the parser misses narrow eyes; a box between brows and nose is used instead
    "facial_hair": (),  # no beard class; a box over the lower face is used instead
}
FACE_CLASSES = (SKIN, *BROWS, NOSE)
MIN_FACE_OVERLAP = 0.85  # below this the edit moved the face, and pasting back would misalign


class Parser(Protocol):
    def parse(self, img: Image.Image) -> np.ndarray: ...  # PARSE_SIZE x PARSE_SIZE class ids


class FaceParser:
    """BiSeNet exported to ONNX (scripts/fetch_face_parser.py), run on CPU."""

    MEAN = np.array([0.485, 0.456, 0.406], np.float32)
    STD = np.array([0.229, 0.224, 0.225], np.float32)

    def __init__(self, model_path: Path):
        import onnxruntime

        self.session = onnxruntime.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def parse(self, img: Image.Image) -> np.ndarray:
        small = img.convert("RGB").resize((PARSE_SIZE, PARSE_SIZE), Image.BILINEAR)
        x = ((np.asarray(small, np.float32) / 255 - self.MEAN) / self.STD).transpose(2, 0, 1)[None]
        return self.session.run(None, {self.input_name: x})[0][0].argmax(0).astype(np.uint8)


def _eyes_box(m: np.ndarray) -> np.ndarray | None:
    brows, nose = np.argwhere(np.isin(m, BROWS)), np.argwhere(m == NOSE)
    if not len(brows) or not len(nose):
        return None
    top, bottom = brows[:, 0].max(), nose[:, 0].min()
    left, right = brows[:, 1].min(), brows[:, 1].max()
    pad = (right - left) * 15 // 200
    box = np.zeros_like(m, bool)
    box[top:max(bottom, top + 1), max(left - pad, 0):right + pad + 1] = True
    return box


def _lower_face_box(m: np.ndarray) -> np.ndarray | None:
    skin, nose = np.argwhere(m == SKIN), np.argwhere(m == NOSE)
    if not len(skin) or not len(nose):
        return None
    top = int(nose[:, 0].mean())  # a moustache starts under the middle of the nose
    bottom = skin[:, 0].max() + PARSE_SIZE // 25  # a beard runs a little past the chin
    box = np.zeros_like(m, bool)
    box[top:bottom + 1, skin[:, 1].min():skin[:, 1].max() + 1] = True
    return box


BOXES = {"eyes": _eyes_box, "facial_hair": _lower_face_box}


def _region_mask(m: np.ndarray, regions: list[str]) -> np.ndarray | None:
    """Pixels of `regions` in one class map; an item that is absent (glasses about to be added)
    adds nothing. None when a box region has no landmarks to anchor it."""
    mask = np.zeros_like(m, bool)
    for r in regions:
        part = BOXES[r](m) if r in BOXES else np.isin(m, REGION_CLASSES[r])
        if part is None:
            return None
        mask |= part
    return mask


def localize(parser: Parser | None, before: bytes, after: bytes, regions: list[str]) -> bytes | None:
    """`after` with everything outside `regions` taken from `before`, or None when that
    cannot be done safely (the caller then keeps the raw edit)."""
    if parser is None or not regions or any(r not in REGION_CLASSES for r in regions):
        return None
    try:
        old = Image.open(io.BytesIO(before)).convert("L")
        new = Image.open(io.BytesIO(after)).convert("L").resize(old.size)
        m_old, m_new = parser.parse(old), parser.parse(new)
        face_old, face_new = np.isin(m_old, FACE_CLASSES), np.isin(m_new, FACE_CLASSES)
        if (face_old & face_new).sum() / max((face_old | face_new).sum(), 1) < MIN_FACE_OVERLAP:
            return None
        a, b = _region_mask(m_old, regions), _region_mask(m_new, regions)
        if a is None or b is None or not (a | b).any():  # the region must show in at least one image
            return None
        grow = PARSE_SIZE // 40
        mask = Image.fromarray(((a | b) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(grow * 2 + 1))
        mask = mask.resize(old.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(max(old.size) // 80))
        out = Image.composite(new, old, mask)
    except Exception:
        log.exception("localize failed; keeping the raw edit")
        return None
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()
