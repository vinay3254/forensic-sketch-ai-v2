from backend.ai.prompts import build_edit_prompt, build_image_prompt
from backend.ai.schemas import Attributes, Edit

DESCRIPTION = "man in his forties, thick hair brushed back, almond-shaped slightly hooded eyes, light stubble"


def test_image_prompt_asks_for_rough_hand_drawn_natural_face():
    p = build_image_prompt(Attributes(gender="male", age_range="early twenties")).lower()
    assert "hand-drawn" in p and "hatching" in p and "not idealised" in p
    for w in ("fine pencil strokes", "realistic proportions", "police", "average-looking", "ordinary"):
        assert w not in p


def test_image_prompt_lists_features_by_name():
    p = build_image_prompt(Attributes(gender="male", age_range="forties", jaw="defined, tapering", eyes="hooded"))
    assert "a male in his forties" not in p  # no "a early..." style gluing
    assert "Jaw: defined, tapering." in p and "Eyes: hooded." in p


def test_image_prompt_carries_the_witness_words():
    p = build_image_prompt(Attributes(gender="male"), DESCRIPTION)
    assert f'"{DESCRIPTION}"' in p


def test_image_prompt_says_left_and_right_are_the_persons_own():
    assert "person's own left" in build_image_prompt(Attributes(marks="mole above the left lip"))


def test_edit_prompt_keeps_rough_hand_drawn_style():
    assert "hand-drawn" in build_edit_prompt([Edit(region="nose", change="wider")]).lower()


def test_witness_words_are_scrubbed_of_crime_words():
    p = build_image_prompt(Attributes(), "The thief was a tall man; the suspect had a scar, like a robber in a mugshot").lower()
    for w in ("thief", "suspect", "robber", "mugshot", "criminal"):
        assert w not in p
    assert "had a scar" in p


def test_generate_passes_typed_description_but_not_interview_words(app, client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    seen = []
    real = app.state.ai_client.generate_image
    app.state.ai_client.generate_image = lambda prompt: (seen.append(prompt), real(prompt))[1]
    client.post(f"/api/cases/{cid}/generate", json={"description": "male, light stubble, crooked nose"})
    assert '"male, light stubble, crooked nose"' in seen[-1]
