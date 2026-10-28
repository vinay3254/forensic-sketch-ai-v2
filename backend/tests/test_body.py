"""Full-body figure drawn from the person details."""

import pytest

from backend.ai.prompts import build_body_prompt
from backend.ai.schemas import Attributes
from backend.cases.details import CaseDetails
from backend.errors import AppError

INCIDENT = {"approach": "came on foot", "weapon": "a revolver", "offence": "robbery", "requesting_unit": "Unit 7"}


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


def draw(client, case_id):
    return client.post(f"/api/cases/{case_id}/body")


def test_prompt_uses_person_details_and_never_incident_details():
    d = CaseDetails(build="heavy, big belly", clothing="yellow t-shirt and shorts", height="1.80 m", **INCIDENT)
    p = build_body_prompt(Attributes(gender="male", age_range="about 30"), d).lower()
    assert "full-length" in p and "about 30 male" in p and "heavy, big belly" in p and "yellow t-shirt and shorts" in p
    for w in ("revolver", "robbery", "on foot", "unit 7", "suspect", "criminal", "mugshot", "police"):
        assert w not in p


def test_prompt_matches_the_head_of_the_sketch():
    p = build_body_prompt(Attributes(hair="bald on top", facial_hair="light stubble"), CaseDetails())
    assert "bald on top" in p and "light stubble" in p


def test_prompt_without_details_is_a_plain_figure():
    p = build_body_prompt(Attributes(), CaseDetails())
    assert "adult person" in p and "None" not in p


def test_draw_stores_and_serves_figure(client, case_id):
    client.put(f"/api/cases/{case_id}/details", json={"build": "slim", **INCIDENT})
    b = draw(client, case_id).json()
    img = client.get(b["image_url"])
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    assert client.get(f"/api/cases/{case_id}/body").json()["id"] == b["id"]


def test_latest_figure_wins(client, case_id):
    draw(client, case_id)
    second = draw(client, case_id).json()
    assert client.get(f"/api/cases/{case_id}/body").json()["id"] == second["id"]


def test_no_figure_is_404(client, case_id):
    assert client.get(f"/api/cases/{case_id}/body").status_code == 404


def test_figure_of_other_case_is_404(client, case_id):
    b = draw(client, case_id).json()
    other = client.post("/api/cases", json={"title": "other"}).json()["id"]
    assert client.get(f"/api/cases/{other}/body/{b['id']}/image").status_code == 404


def test_other_officer_is_denied(client, case_id, login):
    login(client, "officer2", "officer2pass")
    assert draw(client, case_id).status_code == 403


def test_draw_is_audited(client, case_id, login):
    b = draw(client, case_id).json()
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=body_create&case_id={case_id}").json()["items"][0]
    assert row["detail"] == {"outcome": "ok", "body_id": b["id"]}


def test_ai_failure_is_503_and_audited(app, client, case_id, login):
    def boom(prompt):
        raise AppError("AI_UNAVAILABLE", "The AI service did not respond. Try again.", 503)

    app.state.ai_client.generate_image = boom
    assert draw(client, case_id).status_code == 503
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=body_create&case_id={case_id}").json()["items"][0]
    assert row["detail"] == {"outcome": "AI_UNAVAILABLE"}
