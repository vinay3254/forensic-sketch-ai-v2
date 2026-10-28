from backend.ai.prompts import build_edit_prompt, build_image_prompt
from backend.ai.schemas import Attributes, Edit


def test_image_prompt_asks_for_rough_hand_drawn_ordinary_face():
    p = build_image_prompt(Attributes(gender="male", age_range="early twenties")).lower()
    assert "hand-drawn" in p and "ordinary" in p and "hatching" in p
    for w in ("fine pencil strokes", "realistic proportions", "police"):
        assert w not in p


def test_edit_prompt_keeps_rough_hand_drawn_style():
    assert "hand-drawn" in build_edit_prompt([Edit(region="nose", change="wider")]).lower()
