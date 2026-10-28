"""Style library: one click puts a fixed look on the sketch as a new version."""

import pytest
from PIL import Image

from backend.ai.prompts import build_style_prompt
from backend.face.regions import REGION_CLASSES
from backend.styles import catalog
from backend.styles.catalog import BY_KEY, CATEGORIES, regions_of

CRIME = ("suspect", "criminal", "mugshot", "police", "disguise", "thief", "robber")


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


@pytest.fixture
def sketch(client, case_id):
    return client.post(f"/api/cases/{case_id}/generate", json={"description": "male, 30s"}).json()


def apply(client, case_id, **body):
    return client.post(f"/api/cases/{case_id}/style", json=body)


def test_catalog_is_large_unique_and_uses_known_regions():
    keys = [s.key for c in CATEGORIES for s in c.styles]
    assert len(keys) >= 50 and len(keys) == len(set(keys))
    assert {c.key for c in CATEGORIES} == {"clothing", "hair", "facial_hair", "headwear", "eyewear", "accessories"}
    for c in CATEGORIES:
        for s in c.styles:
            assert all(r in REGION_CLASSES for r in regions_of(c, s) or ())


@pytest.mark.parametrize("key", list(BY_KEY))
def test_style_prompts_keep_the_person_and_have_no_crime_words(key):
    c, s = BY_KEY[key]
    p = build_style_prompt(c.label, s.change).lower()
    assert "same person" in p and "hand-drawn" in p
    assert not any(w in p for w in CRIME)


def test_custom_style_text_is_scrubbed():
    assert "thief" not in build_style_prompt("Clothing", "a jacket like the thief wore").lower()


def test_apply_style_makes_a_new_version_and_chat(client, case_id, sketch):
    r = apply(client, case_id, style="kurta")
    assert r.status_code == 200
    v = r.json()["version"]
    assert v["version_no"] == 2 and v["kind"] == "refine" and v["instruction"] == "Style: Kurta"
    chat = client.get(f"/api/cases/{case_id}").json()["chat"]
    assert chat[-2]["content"] == "Style: Kurta" and "Kurta" in chat[-1]["content"]


def test_style_replaces_the_matching_attribute(client, case_id, sketch):
    v = apply(client, case_id, style="buzz_cut").json()["version"]
    assert v["attributes"]["hair"] == "a very short buzz cut"


def test_custom_style_in_a_category(client, case_id, sketch):
    v = apply(client, case_id, category="clothing", text="red checked shirt").json()["version"]
    assert v["instruction"] == "Style: red checked shirt"


@pytest.mark.parametrize(
    "body",
    [{"style": "clown_suit"}, {"category": "shoes", "text": "boots"}, {"category": "clothing", "text": "  "}, {}],
)
def test_bad_requests_are_422(client, case_id, sketch, body):
    assert apply(client, case_id, **body).status_code == 422


def test_no_sketch_is_409(client, case_id):
    r = apply(client, case_id, style="kurta")
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"


def test_other_officer_is_denied(client, case_id, sketch, login):
    login(client, "officer2", "officer2pass")
    assert apply(client, case_id, style="kurta").status_code == 403


def test_apply_is_audited(client, case_id, sketch, login):
    v = apply(client, case_id, style="cap").json()["version"]
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=style_apply&case_id={case_id}").json()["items"][0]
    assert row["version_id"] == v["id"] and row["detail"]["style"] == "cap" and row["detail"]["outcome"] == "ok"


def test_clothing_is_localized_with_the_face_parser(app, client, case_id, sketch):
    from backend.tests.test_regions import FakeParser, face_map

    m = face_map()
    m[440:512, 60:452] = 16  # clothes
    app.state.face_parser = FakeParser(m)
    assert apply(client, case_id, style="hoodie").json()["version"]["localized"] is True


def test_catalog_endpoint_lists_categories_and_present_thumbnails(client, seed_users, login, tmp_path, monkeypatch):
    login(client, "officer1", "officer1pass")
    Image.new("L", (8, 8), 200).save(tmp_path / "kurta.png")
    monkeypatch.setattr(catalog, "ASSETS", tmp_path)
    cats = client.get("/api/styles").json()
    clothing = next(c for c in cats if c["key"] == "clothing")
    kurta = next(s for s in clothing["styles"] if s["key"] == "kurta")
    hoodie = next(s for s in clothing["styles"] if s["key"] == "hoodie")
    assert kurta["image_url"] == "/api/styles/kurta/image" and hoodie["image_url"] is None
    assert client.get("/api/styles/kurta/image").status_code == 200
    assert client.get("/api/styles/hoodie/image").status_code == 404
