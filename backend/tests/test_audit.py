from sqlmodel import Session, select

from backend.models import AuditLog


def test_login_and_failed_login_are_audited(client, seed_users, login):
    client.post("/api/auth/login", json={"username": "officer1", "password": "bad"})
    login(client, "admin", "adminpass")
    items = client.get("/api/audit").json()["items"]
    actions = [i["action"] for i in items]
    assert "login_failed" in actions and "login" in actions
    failed = next(i for i in items if i["action"] == "login_failed")
    assert failed["username"] == "officer1" and failed["user_id"] is None


def test_logout_is_audited(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    client.post("/api/auth/logout")
    login(client, "admin", "adminpass")
    items = client.get("/api/audit?action=logout").json()["items"]
    assert [i["username"] for i in items] == ["officer1"]


def test_officer_cannot_read_audit(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    assert client.get("/api/audit").status_code == 403


def test_chain_verifies_then_detects_tampering(client, seed_users, login, app):
    login(client, "admin", "adminpass")
    client.get("/api/audit")
    assert client.get("/api/audit/verify").json()["ok"] is True
    with Session(app.state.engine) as s:
        row = s.exec(select(AuditLog).order_by(AuditLog.id)).first()
        row.action = "logout"
        s.add(row)
        s.commit()
        bad_id = row.id
    result = client.get("/api/audit/verify").json()
    assert result["ok"] is False and result["first_bad_id"] == bad_id
