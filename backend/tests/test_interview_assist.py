"""Option B: the AI marks which features the free account already covers, as exact quotes only."""

import pytest

from backend.ai.schemas import Coverage
from backend.errors import AppError
from backend.interview.assist import verbatim_coverage

FREE = "He was maybe thirty. His nose was crooked, like it had been broken. Small eyes."


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


def make_interview(client, case_id, free=FREE):
    iv = client.post(f"/api/cases/{case_id}/interviews").json()
    client.put(f"/api/cases/{case_id}/interviews/{iv['id']}", json={"free_recall": free, "free_recall_source": "typed"})
    return iv["id"]


def assist(client, case_id, iid):
    return client.post(f"/api/cases/{case_id}/interviews/{iid}/assist")


def cov(*pairs):
    return Coverage.model_validate({"covered": [{"key": k, "quote": q} for k, q in pairs]})


def test_keeps_only_exact_substrings():
    out = verbatim_coverage(FREE, cov(("nose", "His nose was crooked"), ("eyes", "small, narrow eyes"), ("eyes", "Small eyes")))
    assert out == {"nose": ["His nose was crooked"], "eyes": ["Small eyes"]}


def test_drops_unknown_keys_blank_and_duplicate_quotes_and_orders_by_bank():
    out = verbatim_coverage(
        FREE,
        cov(("eyes", "Small eyes"), ("tattoo", "thirty"), ("nose", "  "), ("age_gender", "maybe thirty"), ("eyes", "Small eyes")),
    )
    assert list(out) == ["age_gender", "eyes"] and out["eyes"] == ["Small eyes"]


def test_quote_is_not_reworded_by_trimming_case_or_punctuation():
    out = verbatim_coverage(FREE, cov(("nose", "his nose was crooked"), ("eyes", "Small eyes.")))
    assert out == {"eyes": ["Small eyes."]}


def test_route_returns_verbatim_quotes(client, case_id):
    r = assist(client, case_id, make_interview(client, case_id))
    assert r.status_code == 200
    covered = r.json()["covered"]
    assert "nose" in covered and all(q in FREE for qs in covered.values() for q in qs)


def test_route_drops_invented_quotes(app, client, case_id):
    app.state.ai_client.find_coverage = lambda free, features: cov(("nose", "a big hooked nose"))
    assert assist(client, case_id, make_interview(client, case_id)).json()["covered"] == {}


def test_assist_is_audited(client, case_id, login):
    iid = make_interview(client, case_id)
    assist(client, case_id, iid)
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=interview_assist&case_id={case_id}").json()["items"]
    assert rows[0]["detail"]["interview_id"] == iid and "nose" in rows[0]["detail"]["keys"]


def test_empty_free_account_is_422(client, case_id):
    r = assist(client, case_id, make_interview(client, case_id, free="   "))
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION"


def test_confirmed_interview_is_409(client, case_id):
    iid = make_interview(client, case_id)
    client.post(f"/api/cases/{case_id}/interviews/{iid}/confirm", json={"witness_confirmed": True})
    r = assist(client, case_id, iid)
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"


def test_ai_failure_is_503_and_interview_is_unchanged(app, client, case_id):
    iid = make_interview(client, case_id)

    def boom(free, features):
        raise AppError("AI_UNAVAILABLE", "The AI service did not respond. Try again.", 503)

    app.state.ai_client.find_coverage = boom
    assert assist(client, case_id, iid).status_code == 503
    assert client.get(f"/api/cases/{case_id}/interviews/{iid}").json()["free_recall"] == FREE


def test_interview_from_other_case_is_404(client, case_id):
    iid = make_interview(client, case_id)
    other = client.post("/api/cases", json={"title": "other"}).json()["id"]
    assert assist(client, other, iid).status_code == 404


def test_other_officer_is_denied(client, case_id, login):
    iid = make_interview(client, case_id)
    login(client, "officer2", "officer2pass")
    assert assist(client, case_id, iid).status_code == 403
