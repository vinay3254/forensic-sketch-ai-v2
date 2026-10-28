"""Sign-up: investigators can create their own account; an admin account needs the admin code."""

import pytest

from backend.app import create_app


@pytest.fixture
def coded(settings):
    settings.admin_signup_code = "letmein-admin-2026"
    return settings


def signup(client, **body):
    return client.post("/api/auth/signup", json={"username": "newbie", "password": "longpassword1", **body})


def test_investigator_signs_up_and_is_logged_in(client):
    r = signup(client, role="officer")
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "officer"
    assert client.get("/api/auth/me").json()["username"] == "newbie"


def test_new_account_can_log_in_again(client):
    signup(client, role="officer")
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "newbie", "password": "longpassword1"}).status_code == 200


def test_admin_needs_the_admin_code(coded):
    from fastapi.testclient import TestClient

    with TestClient(create_app(coded)) as c:
        assert signup(c, role="admin").status_code == 403
        assert signup(c, role="admin", admin_code="wrong").status_code == 403
        r = signup(c, role="admin", admin_code="letmein-admin-2026")
        assert r.status_code == 201 and r.json()["role"] == "admin"


def test_admin_signup_off_without_a_code(client):
    r = signup(client, role="admin", admin_code="anything")
    assert r.status_code == 403 and "not enabled" in r.json()["error"]["message"]


def test_taken_username_is_409(client, seed_users):
    assert client.post("/api/auth/signup", json={"username": "officer1", "password": "longpassword1", "role": "officer"}).status_code == 409


@pytest.mark.parametrize("body", [
    {"username": "ab", "password": "longpassword1", "role": "officer"},
    {"username": "has space", "password": "longpassword1", "role": "officer"},
    {"username": "fine_name", "password": "short", "role": "officer"},
    {"username": "fine_name", "password": "longpassword1", "role": "superuser"},
])
def test_bad_input_is_422(client, body):
    assert client.post("/api/auth/signup", json=body).status_code == 422


def test_signup_is_audited(client, seed_users, login):
    signup(client, role="officer")
    login(client, "admin", "adminpass")
    rows = client.get("/api/audit?action=signup").json()["items"]
    assert rows[0]["username"] == "newbie" and rows[0]["detail"] == {"role": "officer"}


def test_admin_dashboard_has_charts_data(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "Bag theft"}).json()["id"]
    client.post(f"/api/cases/{cid}/generate", json={"description": "male, beard"})
    client.post("/api/auth/login", json={"username": "officer2", "password": "nope"})
    login(client, "admin", "adminpass")
    d = client.get("/api/admin/dashboard?days=7").json()
    assert len(d["daily"]) == 7 and set(d["daily"][-1]["groups"]) == {"sketch", "interview", "casework", "account"}
    today = d["daily"][-1]
    assert today["groups"]["sketch"] >= 1 and today["logins"] >= 2 and today["failed"] >= 1
    o1 = next(p for p in d["people"] if p["username"] == "officer1")
    assert o1["cases"] == 1 and len(o1["daily_actions"]) == 7 and sum(o1["daily_actions"]) >= 3
    assert any(s["username"] == "officer1" for s in d["sessions"])
    assert d["totals"]["failed_logins"] >= 1 and d["totals"]["online"] >= 1
    assert d["recent"][0]["action"]


def test_dashboard_is_admin_only(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    assert client.get("/api/admin/dashboard").status_code == 403
