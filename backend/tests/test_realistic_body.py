"""Realistic body: an MPFB2 human fitted to the full-body picture and textured from front, side and back
views. The live builder (pose detection + Blender) is replaced by a fake; the views come from the AI."""

import pytest

from backend.ai.prompts import VIEW_PROMPTS, scrub
from backend.tests.test_body_model import GLB


@pytest.fixture
def setup(client, app, seed_users, login):
    login(client, "officer1", "officer1pass")
    case_id = client.post("/api/cases", json={"title": "Realistic body"}).json()["id"]
    source = client.post(f"/api/cases/{case_id}/body").json()
    calls = []

    class Builder:
        def build(self, front, views, params):
            calls.append((front, views, params))
            return GLB, b"BLENDER-v1", "fitted to the picture"

    app.state.realistic_builder = Builder()
    return case_id, source, calls


def test_builds_a_saved_model_from_front_side_and_back(client, app, setup):
    case, source, calls = setup
    edits = []
    real = app.state.ai_client.edit_image
    app.state.ai_client.edit_image = lambda image, prompt: (edits.append(prompt), real(image, prompt))[1]
    r = client.post(f"/api/cases/{case}/figure/realistic", json={"body_id": source["id"]})
    assert r.status_code == 200, r.text
    model = r.json()
    front, views, params = calls[0]
    assert front == client.get(source["image_url"]).content
    assert set(views) == {"side", "back"} and all(views.values())
    assert sorted(edits) == sorted(VIEW_PROMPTS.values())
    assert params.height_cm == 172
    assert model["engine"].startswith("Realistic body") and model["blend_url"]
    assert client.get(model["mesh_url"]).content == GLB
    assert client.get(model["blend_url"]).content == b"BLENDER-v1"
    assert client.get(f"/api/cases/{case}/figure/reconstruction").json()["id"] == model["id"]


def test_build_is_audited(client, setup, login):
    case, source, _ = setup
    client.post(f"/api/cases/{case}/figure/realistic", json={})
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=body_realistic&case_id={case}").json()["items"]
    assert rows[0]["detail"]["outcome"] == "ok" and rows[0]["detail"]["body_id"] == source["id"]


def test_off_without_the_builder(client, app, setup):
    case, _, _ = setup
    app.state.realistic_builder = None
    r = client.post(f"/api/cases/{case}/figure/realistic", json={})
    assert r.status_code == 503 and r.json()["error"]["code"] == "REALISTIC_OFF"


def test_needs_a_full_body_image(client, app, seed_users, login):
    login(client, "officer1", "officer1pass")
    case = client.post("/api/cases", json={"title": "empty"}).json()["id"]
    app.state.realistic_builder = object()
    assert client.post(f"/api/cases/{case}/figure/realistic", json={}).status_code == 404


def test_invalid_model_never_replaces_a_saved_one(client, app, setup):
    case, source, _ = setup
    first = client.post(f"/api/cases/{case}/figure/realistic", json={}).json()

    class Broken:
        def build(self, front, views, params):
            return b"not a GLB", b"", ""

    app.state.realistic_builder = Broken()
    assert client.post(f"/api/cases/{case}/figure/realistic", json={}).status_code == 502
    assert client.get(f"/api/cases/{case}/figure/reconstruction").json()["id"] == first["id"]


def test_view_prompts_hold_no_crime_words():
    for p in VIEW_PROMPTS.values():
        assert scrub(p) == p
