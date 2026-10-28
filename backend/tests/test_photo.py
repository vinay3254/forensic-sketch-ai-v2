"""Turning a pencil sketch version into a realistic photo."""

import io

import pytest
from PIL import Image

from backend.ai.prompts import build_photo_prompt
from backend.ai.schemas import Attributes


@pytest.fixture
def version(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    v = client.post(f"/api/cases/{cid}/generate", json={"description": "male"}).json()
    return cid, v


def test_new_version_has_no_photo(version):
    _, v = version
    assert v["photo_url"] is None


def test_make_photo_returns_colour_image(client, version):
    cid, v = version
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/photo")
    assert r.status_code == 200
    photo_url = r.json()["photo_url"]
    assert photo_url == f"/api/cases/{cid}/versions/{v['id']}/photo"
    img = Image.open(io.BytesIO(client.get(photo_url).content))
    assert img.format == "PNG" and img.mode == "RGB"
    assert client.get(f"/api/cases/{cid}").json()["versions"][0]["photo_url"] == photo_url


def test_make_photo_twice_calls_ai_once(client, version, app):
    cid, v = version
    calls = []
    real = app.state.ai_client.edit_image
    app.state.ai_client.edit_image = lambda image, prompt: calls.append(prompt) or real(image, prompt)
    client.post(f"/api/cases/{cid}/versions/{v['id']}/photo")
    client.post(f"/api/cases/{cid}/versions/{v['id']}/photo")
    assert len(calls) == 1


def test_photo_before_it_is_made_is_404(client, version):
    cid, v = version
    r = client.get(f"/api/cases/{cid}/versions/{v['id']}/photo")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_make_photo_is_audited(client, version, login):
    cid, v = version
    client.post(f"/api/cases/{cid}/versions/{v['id']}/photo")
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=make_photo&case_id={cid}").json()["items"]
    assert len(rows) == 1 and rows[0]["version_id"] == v["id"]


def test_other_officer_cannot_make_photo(client, version, login):
    cid, v = version
    login(client, "officer2", "officer2pass")
    assert client.post(f"/api/cases/{cid}/versions/{v['id']}/photo").status_code == 403


def test_failed_photo_leaves_no_file_and_no_photo(client, version, app, settings):
    from backend.errors import AppError

    cid, v = version
    before = sorted(settings.storage_dir.rglob("*.png"))

    def down(image, prompt):
        raise AppError("AI_UNAVAILABLE", "down", 503)

    app.state.ai_client.edit_image = down
    assert client.post(f"/api/cases/{cid}/versions/{v['id']}/photo").status_code == 503
    assert sorted(settings.storage_dir.rglob("*.png")) == before
    assert client.get(f"/api/cases/{cid}").json()["versions"][0]["photo_url"] is None


def test_photo_prompt_carries_colours_and_no_crime_words():
    p = build_photo_prompt(Attributes(skin_tone="medium brown", eyes="dark brown", hair="short black")).lower()
    assert "realistic" in p and "photograph" in p
    assert "medium brown skin" in p and "dark brown" in p and "short black" in p
    for w in ("suspect", "criminal", "mugshot"):
        assert w not in p


def test_photo_prompt_carries_ethnic_appearance():
    p = build_photo_prompt(Attributes(appearance="South Indian", skin_tone="medium brown"))
    assert "ethnic appearance: South Indian" in p
