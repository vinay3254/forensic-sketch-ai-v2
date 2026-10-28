"""Witness confirms the transcript: it locks, and its SHA-256 goes to the audit log."""

import hashlib
import json

import pytest

from backend.interview.transcript import canonical_transcript


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


@pytest.fixture
def interview(client, case_id):
    iv = client.post(f"/api/cases/{case_id}/interviews").json()
    body = {
        "free_recall": "He was maybe thirty. Had a scar, I think.",
        "free_recall_source": "typed",
        "answers": [
            {"key": "eyes", "answer": "narrow, dark?", "status": "uncertain", "source": "speech"},
            {"key": "age_gender", "answer": "a man, about thirty", "status": "remembered", "source": "typed"},
            {"key": "ears", "answer": "", "status": "unknown"},
        ],
    }
    client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json=body)
    return iv["id"]


def confirm(client, case_id, iid, witness_confirmed=True):
    return client.post(f"/api/cases/{case_id}/interviews/{iid}/confirm", json={"witness_confirmed": witness_confirmed})


def test_answers_are_kept_in_question_order(client, case_id, interview):
    keys = [a["key"] for a in client.get(f"/api/cases/{case_id}/interviews/{interview}").json()["answers"]]
    assert keys == ["age_gender", "eyes", "ears"]


def test_confirm_locks_and_records_who_when_and_hash(client, case_id, interview):
    r = confirm(client, case_id, interview)
    assert r.status_code == 200, r.text
    iv = r.json()
    assert iv["status"] == "confirmed" and iv["confirmed_by"] is not None and iv["confirmed_at"]
    expected = hashlib.sha256(canonical_transcript(iv).encode()).hexdigest()
    assert iv["transcript_hash"] == expected


def test_canonical_transcript_covers_the_words(client, case_id, interview):
    iv = client.get(f"/api/cases/{case_id}/interviews/{interview}").json()
    data = json.loads(canonical_transcript(iv))
    assert data["free_recall"] == iv["free_recall"] and data["answers"] == iv["answers"]
    changed = {**iv, "answers": [{**iv["answers"][0], "answer": "a woman"}] + iv["answers"][1:]}
    assert canonical_transcript(changed) != canonical_transcript(iv)


def test_confirm_is_audited_with_hash(client, case_id, interview, login):
    iv = confirm(client, case_id, interview).json()
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=interview_confirm&case_id={case_id}").json()["items"]
    assert rows[0]["detail"] == {"interview_id": interview, "transcript_hash": iv["transcript_hash"]}


def test_confirmed_transcript_cannot_be_edited(client, case_id, interview):
    confirm(client, case_id, interview)
    r = client.put(f"/api/cases/{case_id}/interviews/{interview}", json={"free_recall": "changed"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"
    assert client.get(f"/api/cases/{case_id}/interviews/{interview}").json()["free_recall"].startswith("He was")


def test_confirm_twice_is_409(client, case_id, interview):
    confirm(client, case_id, interview)
    r = confirm(client, case_id, interview)
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"


def test_confirm_needs_the_witness_checkbox(client, case_id, interview):
    r = confirm(client, case_id, interview, witness_confirmed=False)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION"
    assert client.get(f"/api/cases/{case_id}/interviews/{interview}").json()["status"] == "draft"


def test_empty_interview_cannot_be_confirmed(client, case_id):
    iv = client.post(f"/api/cases/{case_id}/interviews").json()
    client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"answers": [{"key": "ears", "status": "unknown"}]})
    r = confirm(client, case_id, iv["id"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION"


def test_other_officer_cannot_confirm(client, case_id, interview, login):
    login(client, "officer2", "officer2pass")
    assert confirm(client, case_id, interview).status_code == 403
