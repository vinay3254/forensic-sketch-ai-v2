import pytest

from backend.errors import AppError


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


def test_generate_creates_v1_with_image(client, case_id):
    v = client.post(f"/api/cases/{case_id}/generate", json={"description": "male, 30s, scar on left cheek"}).json()
    assert v["version_no"] == 1 and v["kind"] == "generate" and v["attributes"]["gender"] == "male"
    img = client.get(v["image_url"])
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"


def test_generate_writes_chat_and_audit(client, case_id, login):
    v = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"}).json()
    chat = client.get(f"/api/cases/{case_id}").json()["chat"]
    assert [m["role"] for m in chat] == ["user", "assistant"] and chat[1]["version_id"] == v["id"]
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=generate&case_id={case_id}").json()["items"]
    assert rows[0]["version_id"] == v["id"]


def test_refine_creates_v2_with_merged_attributes(client, case_id):
    client.post(f"/api/cases/{case_id}/generate", json={"description": "male, 30s"})
    r = client.post(f"/api/cases/{case_id}/refine", json={"message": "make the jaw wider"}).json()
    assert r["version"]["version_no"] == 2 and "wider" in r["version"]["attributes"]["jaw"]


def test_unclear_refine_creates_no_version(client, case_id):
    client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    r = client.post(f"/api/cases/{case_id}/refine", json={"message": "hmm not quite"}).json()
    assert r["version"] is None and r["reply"]
    assert len(client.get(f"/api/cases/{case_id}/versions").json()) == 1


def test_refine_before_generate_is_409(client, case_id):
    r = client.post(f"/api/cases/{case_id}/refine", json={"message": "wider jaw"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"


def test_revert_copies_old_version_as_new(client, case_id):
    v1 = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"}).json()
    client.post(f"/api/cases/{case_id}/refine", json={"message": "bigger nose"})
    v3 = client.post(f"/api/cases/{case_id}/versions/{v1['id']}/revert").json()
    assert v3["version_no"] == 3 and v3["kind"] == "revert" and v3["attributes"] == v1["attributes"]
    assert client.get(v3["image_url"]).content == client.get(v1["image_url"]).content


def test_duplicate_version_no_is_409(client, case_id, monkeypatch):
    client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    import backend.face.service as svc

    monkeypatch.setattr(svc, "latest_version", lambda session, cid: None)  # stale read, as in a race
    r = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"
    monkeypatch.undo()
    v = client.get(f"/api/cases/{case_id}/versions").json()
    assert len(v) == 1 and client.get(v[0]["image_url"]).status_code == 200


def test_description_over_2000_chars_is_422(client, case_id):
    r = client.post(f"/api/cases/{case_id}/generate", json={"description": "a" * 2001})
    assert r.status_code == 422


def test_ai_failure_creates_no_version(client, case_id, app):
    class Down:
        def extract_attributes(self, t):
            raise AppError("AI_UNAVAILABLE", "down", 503)

    app.state.ai_client = Down()
    r = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    assert r.status_code == 503
    assert client.get(f"/api/cases/{case_id}/versions").json() == []


def test_other_officer_cannot_fetch_image(client, case_id, login):
    v = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"}).json()
    login(client, "officer2", "officer2pass")
    assert client.get(v["image_url"]).status_code == 403


def test_version_from_other_case_is_404(client, case_id):
    v = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"}).json()
    other = client.post("/api/cases", json={"title": "u"}).json()["id"]
    assert client.get(f"/api/cases/{other}/versions/{v['id']}/image").status_code == 404
