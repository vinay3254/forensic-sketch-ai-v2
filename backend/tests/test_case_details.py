"""Person and incident details on a case, and the body questions in the interview."""

import pytest

from backend.cases.details import prefill_from_interview


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


def put(client, case_id, body):
    return client.put(f"/api/cases/{case_id}/details", json=body)


def test_details_round_trip(client, case_id):
    body = {"height": "1.75 to 1.85 m", "build": "heavy", "weapon": "a revolver", "offence": "robbery"}
    r = put(client, case_id, body)
    assert r.status_code == 200 and r.json()["height"] == "1.75 to 1.85 m"
    assert client.get(f"/api/cases/{case_id}").json()["case"]["details"] == body


def test_put_replaces_and_drops_blank_fields(client, case_id):
    put(client, case_id, {"height": "tall", "build": "slim"})
    put(client, case_id, {"height": "tall", "build": "  "})
    assert client.get(f"/api/cases/{case_id}").json()["case"]["details"] == {"height": "tall"}


def test_new_case_has_empty_details(client, case_id):
    assert client.get(f"/api/cases/{case_id}").json()["case"]["details"] == {}


def test_text_over_500_chars_is_422(client, case_id):
    assert put(client, case_id, {"clothing": "x" * 501}).status_code == 422
    assert client.get(f"/api/cases/{case_id}").json()["case"]["details"] == {}


def test_unknown_key_is_422(client, case_id):
    assert put(client, case_id, {"shoe_size": "44"}).status_code == 422


def test_other_officer_is_denied(client, case_id, login):
    login(client, "officer2", "officer2pass")
    assert put(client, case_id, {"height": "tall"}).status_code == 403


def test_update_is_audited_with_changed_keys(client, case_id, login):
    put(client, case_id, {"height": "tall", "build": "slim"})
    put(client, case_id, {"height": "tall", "build": "heavy", "approach": "on foot"})
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=case_update&case_id={case_id}").json()["items"][0]
    assert row["detail"]["keys"] == ["approach", "build"]


ANSWERS = [
    {"key": "height", "answer": "about my height, maybe 1.80", "status": "remembered"},
    {"key": "build", "answer": "big belly", "status": "uncertain"},
    {"key": "clothing", "answer": "", "status": "unknown"},
    {"key": "voice", "answer": "rural accent", "status": "unknown"},
    {"key": "movement", "answer": "  ", "status": "remembered"},
]


def test_prefill_fills_empty_fields_verbatim_and_skips_unknown_and_blank():
    out = prefill_from_interview({}, ANSWERS)
    assert out == {"height": "about my height, maybe 1.80", "build": "big belly"}


def test_prefill_never_overwrites_what_the_officer_typed():
    out = prefill_from_interview({"height": "1.75 m", "weapon": "knife"}, ANSWERS)
    assert out["height"] == "1.75 m" and out["build"] == "big belly" and out["weapon"] == "knife"


def test_generate_from_interview_prefills_case_details(client, case_id):
    put(client, case_id, {"height": "officer note"})
    iv = client.post(f"/api/cases/{case_id}/interviews").json()
    client.put(
        f"/api/cases/{case_id}/interviews/{iv['id']}",
        json={"free_recall": "A man.", "answers": [{**a, "source": "typed"} for a in ANSWERS]},
    )
    client.post(f"/api/cases/{case_id}/interviews/{iv['id']}/confirm", json={"witness_confirmed": True})
    assert client.post(f"/api/cases/{case_id}/interviews/{iv['id']}/generate").status_code == 200
    assert client.get(f"/api/cases/{case_id}").json()["case"]["details"] == {"height": "officer note", "build": "big belly"}
