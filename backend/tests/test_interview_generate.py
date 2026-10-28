"""Generating the first sketch from a confirmed witness interview."""

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.ai.schemas import Attributes
from backend.interview.transcript import FIELDS_FOR, render_description


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


ANSWERS = [
    {"key": "age_gender", "answer": "a man, maybe thirty", "status": "remembered", "source": "typed"},
    {"key": "eyes", "answer": "narrow, dark? not sure", "status": "uncertain", "source": "speech"},
    {"key": "ears", "answer": "", "status": "unknown"},
    {"key": "facial_hair", "answer": "some stubble", "status": "uncertain", "source": "typed"},
]


def make_interview(client, case_id, confirm=True):
    iv = client.post(f"/api/cases/{case_id}/interviews").json()
    body = {"free_recall": "He had big ears and a scar on his cheek.", "free_recall_source": "typed", "answers": ANSWERS}
    client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json=body)
    if confirm:
        client.post(f"/api/cases/{case_id}/interviews/{iv['id']}/confirm", json={"witness_confirmed": True})
    return client.get(f"/api/cases/{case_id}/interviews/{iv['id']}").json()


def generate(client, case_id, iid):
    return client.post(f"/api/cases/{case_id}/interviews/{iid}/generate")


def test_description_keeps_words_and_labels_certainty(client, case_id):
    iv = make_interview(client, case_id)
    d = render_description(iv)
    assert 'Free account: "He had big ears and a scar on his cheek."' in d
    assert 'Age and gender (remembered): "a man, maybe thirty"' in d
    assert 'Eyes (uncertain): "narrow, dark? not sure"' in d
    assert "Ears: not remembered" in d
    assert "Nose" not in d  # not asked: left to the free account


def test_draft_interview_cannot_generate(client, case_id):
    iv = make_interview(client, case_id, confirm=False)
    r = generate(client, case_id, iv["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"


def test_generate_creates_version_linked_to_interview(client, case_id, app):
    seen = []
    real = app.state.ai_client.extract_attributes
    app.state.ai_client.extract_attributes = lambda t: seen.append(t) or real(t)
    iv = make_interview(client, case_id)
    r = generate(client, case_id, iv["id"])
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["version_no"] == 1 and v["kind"] == "generate" and v["interview_id"] == iv["id"]
    assert v["instruction"] == f"From witness interview #{iv['id']}"
    assert seen == [render_description(iv)]


def test_unknown_features_are_blank_even_if_free_account_mentions_them(client, case_id, app):
    app.state.ai_client.extract_attributes = lambda t: Attributes(gender="male", ears="big", eyes="narrow")
    iv = make_interview(client, case_id)
    attrs = generate(client, case_id, iv["id"]).json()["attributes"]
    assert attrs["ears"] is None and attrs["eyes"] == "narrow"


def test_uncertain_fields_are_flagged_on_the_version(client, case_id):
    iv = make_interview(client, case_id)
    v = generate(client, case_id, iv["id"]).json()
    assert sorted(v["uncertain"]) == ["eyes", "facial_hair"]
    assert client.get(f"/api/cases/{case_id}").json()["versions"][0]["uncertain"] == v["uncertain"]


def test_generate_is_audited_and_chat_names_the_interview(client, case_id, login):
    iv = make_interview(client, case_id)
    v = generate(client, case_id, iv["id"]).json()
    chat = client.get(f"/api/cases/{case_id}").json()["chat"]
    assert chat[0]["content"] == f"Witness interview #{iv['id']} (confirmed)"
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=generate&case_id={case_id}").json()["items"][0]
    assert row["version_id"] == v["id"] and row["detail"] == {"outcome": "ok", "interview_id": iv["id"]}


def test_refine_keeps_uncertainty_except_for_the_edited_feature(client, case_id):
    iv = make_interview(client, case_id)
    generate(client, case_id, iv["id"])
    v2 = client.post(f"/api/cases/{case_id}/refine", json={"message": "make the eyes wider"}).json()["version"]
    assert v2["uncertain"] == ["facial_hair"]


def test_other_officer_cannot_generate(client, case_id, login):
    iv = make_interview(client, case_id)
    login(client, "officer2", "officer2pass")
    assert generate(client, case_id, iv["id"]).status_code == 403


def test_field_map_covers_every_question():
    from backend.interview.questions import EXTRAS, FEATURES

    assert set(FIELDS_FOR) == {q["key"] for q in FEATURES + EXTRAS}
    assert all(set(f) <= set(Attributes.model_fields) for f in FIELDS_FOR.values())


def test_missing_columns_are_added_to_an_existing_database(tmp_path):
    from backend.db import init_db

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as c:  # a faceversion table from before interview_id/uncertain existed
        c.execute(text(
            "CREATE TABLE faceversion (id INTEGER PRIMARY KEY, case_id INTEGER, parent_id INTEGER, version_no INTEGER,"
            " kind VARCHAR, instruction VARCHAR, attributes JSON, prompt VARCHAR, image_path VARCHAR,"
            " photo_path VARCHAR, created_by INTEGER, created_at DATETIME)"
        ))
    init_db(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("faceversion")}
    assert {"interview_id", "uncertain"} <= cols
