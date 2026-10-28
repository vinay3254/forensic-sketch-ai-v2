"""Disguise variants: the same face with a cap, glasses, a beard and so on."""

import pytest

from backend.ai.prompts import VARIANTS, build_variant_prompt
from backend.errors import AppError


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


@pytest.fixture
def version(client, case_id):
    return client.post(f"/api/cases/{case_id}/generate", json={"description": "male, 30s"}).json()


def make(client, case_id, version_id, kind="cap"):
    return client.post(f"/api/cases/{case_id}/versions/{version_id}/variants", json={"kind": kind})


def test_create_returns_variant_with_image(client, case_id, version):
    r = make(client, case_id, version["id"], "glasses")
    assert r.status_code == 200
    v = r.json()
    assert v["kind"] == "glasses" and v["label"] == "Glasses" and v["version_no"] == 1 and v["localized"] is False
    img = client.get(v["image_url"])
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"


def test_list_is_newest_first(client, case_id, version):
    make(client, case_id, version["id"], "cap")
    make(client, case_id, version["id"], "hood")
    assert [v["kind"] for v in client.get(f"/api/cases/{case_id}/variants").json()] == ["hood", "cap"]


def test_unknown_kind_is_422(client, case_id, version):
    assert make(client, case_id, version["id"], "clown_nose").status_code == 422


def test_version_of_other_case_is_404(client, case_id, version):
    other = client.post("/api/cases", json={"title": "other"}).json()["id"]
    assert make(client, other, version["id"]).status_code == 404


def test_variant_image_of_other_case_is_404(client, case_id, version):
    v = make(client, case_id, version["id"]).json()
    other = client.post("/api/cases", json={"title": "other"}).json()["id"]
    assert client.get(f"/api/cases/{other}/variants/{v['id']}/image").status_code == 404


def test_other_officer_is_denied(client, case_id, version, login):
    login(client, "officer2", "officer2pass")
    assert make(client, case_id, version["id"]).status_code == 403


def test_create_is_audited(client, case_id, version, login):
    v = make(client, case_id, version["id"], "stubble").json()
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=variant_create&case_id={case_id}").json()["items"][0]
    assert row["version_id"] == version["id"] and row["detail"]["kind"] == "stubble" and row["detail"]["outcome"] == "ok"
    assert row["detail"]["variant_id"] == v["id"]


def test_ai_failure_is_503_and_audited(app, client, case_id, version, login):
    def boom(image, prompt):
        raise AppError("AI_UNAVAILABLE", "The AI service did not respond. Try again.", 503)

    app.state.ai_client.edit_image = boom
    assert make(client, case_id, version["id"]).status_code == 503
    assert client.get(f"/api/cases/{case_id}/variants").json() == []
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=variant_create&case_id={case_id}").json()["items"][0]
    assert row["detail"]["outcome"] == "AI_UNAVAILABLE"


def test_localized_with_face_parser(app, client, case_id, version):
    from backend.tests.test_regions import FakeParser, face_map

    app.state.face_parser = FakeParser(face_map(glasses=True))
    assert make(client, case_id, version["id"], "glasses").json()["localized"] is True


@pytest.mark.parametrize("kind", list(VARIANTS))
def test_variant_prompt_keeps_identity_and_has_no_crime_words(kind):
    p = build_variant_prompt(kind).lower()
    assert "same person" in p and "hand-drawn" in p
    for w in ("suspect", "criminal", "mugshot", "police", "disguise"):
        assert w not in p
