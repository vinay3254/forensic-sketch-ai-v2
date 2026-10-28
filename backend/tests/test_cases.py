def test_create_and_list_own_cases(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    c = client.post("/api/cases", json={"title": "Chain snatching, Yelahanka"}).json()
    assert c["case_number"].startswith("BLR-2026-")
    assert [x["id"] for x in client.get("/api/cases").json()] == [c["id"]]


def test_case_numbers_increment(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    a = client.post("/api/cases", json={"title": "a"}).json()["case_number"]
    b = client.post("/api/cases", json={"title": "b"}).json()["case_number"]
    assert a.endswith("-0001") and b.endswith("-0002")


def test_other_officer_gets_403_and_access_denied_is_audited(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    login(client, "officer2", "officer2pass")
    r = client.get(f"/api/cases/{cid}")
    assert r.status_code == 403
    assert client.get("/api/cases").json() == []
    login(client, "admin", "adminpass")
    denied = client.get(f"/api/audit?action=access_denied&case_id={cid}").json()["items"]
    assert len(denied) == 1 and denied[0]["username"] == "officer2"


def test_admin_sees_all_cases_and_open_is_audited(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    login(client, "admin", "adminpass")
    assert len(client.get("/api/cases").json()) == 1
    detail = client.get(f"/api/cases/{cid}").json()
    assert detail["case"]["id"] == cid and detail["versions"] == [] and detail["chat"] == []
    opened = client.get(f"/api/audit?action=case_open&case_id={cid}").json()["items"]
    assert len(opened) == 1


def test_missing_case_is_404(client, seed_users, login):
    login(client, "admin", "adminpass")
    assert client.get("/api/cases/999").json()["error"]["code"] == "NOT_FOUND"


def test_empty_title_is_422(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    assert client.post("/api/cases", json={"title": ""}).status_code == 422
