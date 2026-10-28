"""Starting, saving and reading an interview draft."""

import pytest
from sqlmodel import Session

from backend.interview.questions import FEATURES
from backend.models import Interview


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


def start(client, case_id):
    r = client.post(f"/api/cases/{case_id}/interviews")
    assert r.status_code == 200, r.text
    return r.json()


def test_start_creates_empty_draft(client, case_id):
    iv = start(client, case_id)
    assert iv["status"] == "draft" and iv["case_id"] == case_id
    assert iv["free_recall"] == "" and iv["answers"] == [] and iv["transcript_hash"] is None


def test_start_is_audited(client, case_id, login):
    iv = start(client, case_id)
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=interview_start&case_id={case_id}").json()["items"]
    assert len(rows) == 1 and rows[0]["detail"] == {"interview_id": iv["id"]}


def test_save_keeps_words_verbatim_and_fills_prompt_from_bank(client, case_id):
    iv = start(client, case_id)
    words = "  umm he had, like, REALLY bushy eyebrows... i think?  "
    body = {
        "free_recall": "He was maybe thirty-ish.\nHad a scar, I'm fairly sure.",
        "free_recall_source": "speech",
        "answers": [{"key": "eyebrows", "answer": words, "status": "uncertain", "source": "typed"}],
    }
    r = client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json=body)
    assert r.status_code == 200, r.text
    saved = client.get(f"/api/cases/{case_id}/interviews/{iv['id']}").json()
    assert saved["free_recall"] == body["free_recall"] and saved["free_recall_source"] == "speech"
    eyebrows_prompt = next(f["prompt"] for f in FEATURES if f["key"] == "eyebrows")
    assert saved["answers"] == [
        {"key": "eyebrows", "prompt": eyebrows_prompt, "answer": words, "status": "uncertain", "source": "typed"}
    ]


def test_client_cannot_change_prompt_wording(client, case_id):
    iv = start(client, case_id)
    body = {"answers": [{"key": "eyes", "prompt": "Were the eyes dark?", "answer": "yes", "status": "remembered"}]}
    client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json=body)
    saved = client.get(f"/api/cases/{case_id}/interviews/{iv['id']}").json()
    assert saved["answers"][0]["prompt"] != "Were the eyes dark?"


def test_unknown_question_key_is_422(client, case_id):
    iv = start(client, case_id)
    r = client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"answers": [{"key": "tattoo_colour", "answer": "x"}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION"


def test_duplicate_question_key_is_422(client, case_id):
    iv = start(client, case_id)
    answers = [{"key": "nose", "answer": "a"}, {"key": "nose", "answer": "b"}]
    assert client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"answers": answers}).status_code == 422


def test_bad_status_is_422(client, case_id):
    iv = start(client, case_id)
    answers = [{"key": "nose", "answer": "a", "status": "probably"}]
    assert client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"answers": answers}).status_code == 422


def test_answer_over_2000_chars_is_422(client, case_id):
    iv = start(client, case_id)
    answers = [{"key": "nose", "answer": "a" * 2001}]
    assert client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"answers": answers}).status_code == 422


def test_confirmed_interview_cannot_be_edited(client, case_id, app):
    iv = start(client, case_id)
    with Session(app.state.engine) as s:
        row = s.get(Interview, iv["id"])
        row.status = "confirmed"
        s.add(row)
        s.commit()
    r = client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"free_recall": "changed"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"


def test_list_returns_case_interviews_newest_first(client, case_id):
    a, b = start(client, case_id), start(client, case_id)
    ids = [i["id"] for i in client.get(f"/api/cases/{case_id}/interviews").json()]
    assert ids == [b["id"], a["id"]]


def test_interview_from_other_case_is_404(client, case_id):
    iv = start(client, case_id)
    other = client.post("/api/cases", json={"title": "other"}).json()["id"]
    r = client.get(f"/api/cases/{other}/interviews/{iv['id']}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_other_officer_is_denied_and_audited(client, case_id, login):
    iv = start(client, case_id)
    login(client, "officer2", "officer2pass")
    assert client.get(f"/api/cases/{case_id}/interviews/{iv['id']}").status_code == 403
    assert client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"free_recall": "x"}).status_code == 403
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=access_denied&case_id={case_id}").json()["items"]
    assert len(rows) == 2


def test_optional_extras_are_saved_with_their_bank_prompt(client, case_id):
    from backend.interview.questions import EXTRAS

    iv = start(client, case_id)
    answers = [
        {"key": "facial_hair", "answer": "some stubble i think", "status": "uncertain", "source": "speech"},
        {"key": "distinguishing_features", "answer": "a cut above his left eyebrow", "status": "remembered"},
    ]
    client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"answers": answers})
    saved = {a["key"]: a for a in client.get(f"/api/cases/{case_id}/interviews/{iv['id']}").json()["answers"]}
    bank = {e["key"]: e["prompt"] for e in EXTRAS}
    assert saved["facial_hair"]["prompt"] == bank["facial_hair"] and saved["facial_hair"]["answer"] == "some stubble i think"
    assert saved["distinguishing_features"]["status"] == "remembered"
