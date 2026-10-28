import io

import numpy as np
import pytest
from PIL import Image

from backend.face.regions import localize

SKIN, L_BROW, R_BROW, NOSE, HAIR = 1, 2, 3, 10, 17


def face_map(nose=True, shift=0):
    m = np.zeros((512, 512), np.uint8)
    m[40:120, 100:412] = HAIR
    m[120 + shift:420 + shift, 140:372] = SKIN
    m[180 + shift:195 + shift, 170:240] = L_BROW
    m[180 + shift:195 + shift, 272:342] = R_BROW
    if nose:
        m[240 + shift:300 + shift, 226:286] = NOSE
    return m


class FakeParser:
    def __init__(self, *maps):
        self.maps = list(maps)

    def parse(self, img):
        return self.maps.pop(0) if len(self.maps) > 1 else self.maps[0]


def png(value, size=(256, 384)):
    buf = io.BytesIO()
    Image.new("L", size, value).save(buf, "PNG")
    return buf.getvalue()


def at(data, x, y):
    """Pixel at (x, y) given in 512x512 parser coordinates."""
    img = Image.open(io.BytesIO(data))
    return img.getpixel((x * img.width // 512, y * img.height // 512))


def test_keeps_edit_inside_region_and_original_outside():
    out = localize(FakeParser(face_map()), png(200), png(50), ["nose"])
    assert at(out, 256, 270) == 50  # nose: edited
    assert at(out, 256, 80) == 200 and at(out, 20, 500) == 200  # hair, background: original


def test_eyes_use_box_between_brows_and_nose():
    out = localize(FakeParser(face_map()), png(200), png(50), ["eyes"])
    assert at(out, 205, 215) == 50 and at(out, 307, 215) == 50
    assert at(out, 256, 380) == 200  # chin untouched


def test_combines_regions():
    out = localize(FakeParser(face_map()), png(200), png(50), ["nose", "hair"])
    assert at(out, 256, 270) == 50 and at(out, 256, 80) == 50 and at(out, 20, 500) == 200


@pytest.mark.parametrize("regions", [["jaw"], ["nose", "facial_hair"], ["marks"], []])
def test_unmapped_regions_return_none(regions):
    assert localize(FakeParser(face_map()), png(200), png(50), regions) is None


def test_region_not_found_returns_none():
    assert localize(FakeParser(face_map(nose=False)), png(200), png(50), ["nose"]) is None


def test_moved_face_returns_none():
    assert localize(FakeParser(face_map(), face_map(shift=80)), png(200), png(50), ["nose"]) is None


def test_parser_error_returns_none():
    class Broken:
        def parse(self, img):
            raise RuntimeError("boom")

    assert localize(Broken(), png(200), png(50), ["nose"]) is None


def test_no_parser_returns_none():
    assert localize(None, png(200), png(50), ["nose"]) is None
