import io

from PIL import Image, ImageStat

from backend.ai.prompts import build_edit_prompt, build_image_prompt
from backend.ai.schemas import Attributes, Edit
from backend.face.service import finish_sketch, scanned_finish


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_image_prompt_asks_for_rough_hand_drawn_ordinary_face():
    p = build_image_prompt(Attributes(gender="male", age_range="early twenties")).lower()
    assert "hand-drawn" in p and "ordinary" in p and "hatching" in p
    for w in ("fine pencil strokes", "realistic proportions", "police"):
        assert w not in p


def test_edit_prompt_keeps_rough_hand_drawn_style():
    assert "hand-drawn" in build_edit_prompt([Edit(region="nose", change="wider")]).lower()


def test_scanned_finish_tints_paper_and_adds_grain():
    out = Image.open(io.BytesIO(scanned_finish(_png(Image.new("L", (64, 96), 255)))))
    stat = ImageStat.Stat(out)
    assert out.mode == "L" and out.size == (64, 96)
    assert stat.mean[0] < 245 and stat.stddev[0] > 0


def test_scanned_finish_keeps_dark_lines_dark():
    out = Image.open(io.BytesIO(scanned_finish(_png(Image.new("L", (16, 16), 0)))))
    assert ImageStat.Stat(out).mean[0] < 60


def test_finish_sketch_follows_setting(settings):
    data = _png(Image.new("L", (16, 16), 255))
    assert finish_sketch(settings, data) == data
    scanned = settings.model_copy(update={"sketch_finish": "scanned"})
    assert finish_sketch(scanned, data) != data
