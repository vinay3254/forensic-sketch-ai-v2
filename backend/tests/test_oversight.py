"""Admin oversight: each admin supervises the investigators assigned to them and sees their
logins, sessions, cases and everything they did, built from the audit log."""

import pytest
from sqlmodel import Session, select

from backend.auth.security import hash_password
from backend.models import User


@pytest.fixture
def users(app, client, seed_users):
    with Session(app.state.engine) as s:
        s.add(User(username="admin2", password_hash=hash_password("admin2pass"), role="admin"))
        s.commit()
        return {u.username: u.id for u in s.exec(select(User)).all()}


def as_(client, login, who):
    login(client, who, f"{who}pass")
    return client


def officer_day(client, login):
    """officer1: one finished session with a case, then a second one still open."""
    as_(client, login, "officer1")
    cid = client.post("/api/cases", json={"title": "Bag theft"}).json()["id"]
    client.post(f"/api/cases/{cid}/generate", json={"description": "male, thick moustache"})
    client.post("/api/auth/logout")
    as_(client, login, "officer1")
    client.get(f"/api/cases/{cid}")
    return cid


def row(overview, name):
    return next(u for u in overview["team"] + overview["admins"] if u["username"] == name)


def test_only_admins(client, users, login):
    as_(client, login, "officer1")
    assert client.get("/api/admin/overview").status_code == 403


def test_overview_counts_logins_logouts_cases_and_failures(client, users, login):
    cid = officer_day(client, login)
    client.post("/api/auth/login", json={"username": "officer1", "password": "wrong"})
    as_(client, login, "admin")
    o = client.get("/api/admin/overview").json()
    r = row(o, "officer1")
    assert r["logins"] == 2 and r["logouts"] == 1 and r["failed_logins"] == 1
    assert r["active_now"] is True  # the second session was never logged out and has not expired
    assert r["cases"] == 1 and r["sessions"] == 2 and r["last_login"] and r["last_logout"]
    assert r["actions"] >= 4
    assert o["totals"]["failed_logins"] >= 1 and cid


def test_active_now_while_logged_in(client, users, login):
    as_(client, login, "officer2")
    client.post("/api/cases", json={"title": "x"})
    from fastapi.testclient import TestClient

    other = TestClient(client.app)
    login(other, "admin", "adminpass")
    assert row(other.get("/api/admin/overview").json(), "officer2")["active_now"] is True


def test_admin_sees_assigned_and_unassigned_investigators_and_all_admins(client, users, login):
    as_(client, login, "admin")
    r = client.put(f"/api/admin/users/{users['officer1']}/supervisor", json={"admin_id": users["admin2"]})
    assert r.status_code == 200 and r.json()["supervisor_id"] == users["admin2"]
    team = [u["username"] for u in client.get("/api/admin/overview").json()["team"]]
    assert "officer1" not in team and "officer2" in team  # officer2 has no admin yet: every admin sees them
    as_(client, login, "admin2")
    o = client.get("/api/admin/overview").json()
    assert "officer1" in [u["username"] for u in o["team"]]
    assert {"admin", "admin2"} <= {u["username"] for u in o["admins"]}
    assert row(o, "officer1")["supervisor"] == "admin2"


def test_someone_elses_investigator_is_denied_and_audited(client, users, login):
    as_(client, login, "admin2")
    client.put(f"/api/admin/users/{users['officer1']}/supervisor", json={"admin_id": users["admin2"]})
    as_(client, login, "admin")
    r = client.get(f"/api/admin/users/{users['officer1']}/sessions")
    assert r.status_code == 403
    rows = client.get("/api/audit?action=access_denied").json()["items"]
    assert rows[0]["detail"]["user_id"] == users["officer1"]


def test_supervisor_must_be_an_admin_and_target_an_investigator(client, users, login):
    as_(client, login, "admin")
    assert client.put(f"/api/admin/users/{users['officer1']}/supervisor", json={"admin_id": users["officer2"]}).status_code == 422
    assert client.put(f"/api/admin/users/{users['admin2']}/supervisor", json={"admin_id": users["admin"]}).status_code == 422
    r = client.put(f"/api/admin/users/{users['officer1']}/supervisor", json={"admin_id": None})
    assert r.status_code == 200 and r.json()["supervisor_id"] is None


def test_assignment_is_audited(client, users, login):
    as_(client, login, "admin")
    client.put(f"/api/admin/users/{users['officer1']}/supervisor", json={"admin_id": users["admin2"]})
    rows = client.get("/api/audit?action=supervisor_assign").json()["items"]
    assert rows[0]["detail"] == {"user_id": users["officer1"], "from": None, "to": users["admin2"]}


def test_sessions_run_from_login_to_logout_with_what_happened(client, users, login):
    officer_day(client, login)
    as_(client, login, "admin")
    s = client.get(f"/api/admin/users/{users['officer1']}/sessions").json()
    assert len(s) == 2  # newest first
    first = s[1]
    assert first["end_reason"] == "logout" and first["end"]
    assert first["by_action"]["case_create"] == 1 and first["by_action"]["generate"] == 1
    assert [c["title"] for c in first["cases"]] == ["Bag theft"]
    assert s[0]["end_reason"] == "active" and s[0]["end"] is None


def test_session_timeline_lists_every_row_in_order(client, users, login):
    officer_day(client, login)
    as_(client, login, "admin")
    first = client.get(f"/api/admin/users/{users['officer1']}/sessions").json()[1]
    rows = client.get(f"/api/admin/users/{users['officer1']}/sessions/{first['id']}").json()
    actions = [r["action"] for r in rows]
    assert actions[0] == "login" and actions[-1] == "logout" and "case_create" in actions
    assert [r["id"] for r in rows] == sorted(r["id"] for r in rows)


def test_cases_handled_by_an_investigator(client, users, login):
    cid = officer_day(client, login)
    as_(client, login, "admin")
    cases = client.get(f"/api/admin/users/{users['officer1']}/cases").json()
    assert cases[0]["case_id"] == cid and cases[0]["owned"] is True
    assert cases[0]["by_action"]["generate"] == 1 and cases[0]["first"] <= cases[0]["last"]


def test_oversight_views_are_audited(client, users, login):
    as_(client, login, "admin")
    client.get("/api/admin/overview")
    client.get(f"/api/admin/users/{users['officer2']}/sessions")
    views = [r["detail"]["view"] for r in client.get("/api/audit?action=oversight_view").json()["items"]]
    assert views[:2] == ["sessions", "overview"]
