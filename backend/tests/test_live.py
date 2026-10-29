"""Live dashboard: who is active right now and on which page, work in progress, and a change signal."""

import time

from backend.live import Changes, page_label, task_label


def test_heartbeat_marks_a_user_active_on_a_page(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "Bag theft"}).json()["id"]
    assert client.post("/api/auth/heartbeat", json={"page": f"/cases/{cid}/figure"}).status_code == 204
    login(client, "admin", "adminpass")
    p = next(p for p in client.get("/api/admin/dashboard").json()["people"] if p["username"] == "officer1")
    assert p["status"] == "active" and p["page"].startswith("Figure · BLR-")


def test_idle_and_signed_out(client, app, seed_users, login):
    login(client, "officer1", "officer1pass")
    client.post("/api/auth/heartbeat", json={"page": "/cases"})
    app.state.presence.seen[next(iter(app.state.presence.seen))] = (time.time() - 600, "/cases")
    login(client, "officer2", "officer2pass")
    client.post("/api/auth/logout")
    login(client, "admin", "adminpass")
    people = {p["username"]: p for p in client.get("/api/admin/dashboard").json()["people"]}
    assert people["officer1"]["status"] == "idle"
    assert people["officer2"]["status"] == "signed_out"


def test_work_in_progress_is_listed(client, app, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "Bag theft"}).json()["id"]
    uid = client.get("/api/auth/me").json()["id"]
    app.state.presence.start(uid, "POST", f"/api/cases/{cid}/generate")
    login(client, "admin", "adminpass")
    d = client.get("/api/admin/dashboard").json()
    task = d["in_progress"][0]
    assert task["username"] == "officer1" and task["label"] == "Generating a sketch" and task["case_number"]
    assert next(p for p in d["people"] if p["username"] == "officer1")["doing"][0]["label"] == "Generating a sketch"


def test_finished_requests_leave_the_list(client, app, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "Bag theft"}).json()["id"]
    client.post(f"/api/cases/{cid}/generate", json={"description": "male"})
    assert app.state.presence.tasks == {}


def test_labels():
    assert task_label("POST", "/api/cases/3/refine") == "Refining the sketch"
    assert task_label("POST", "/api/cases/3/figure/realistic") == "Building the 3D body"
    assert task_label("GET", "/api/cases/3") is None
    assert page_label("/cases/3/interviews/9") == "Interview"
    assert page_label("/records") == "Criminal records"


def test_audit_rows_signal_a_change(client, seed_users, login):
    changes: Changes = client.app.state.changes
    before = changes.version
    login(client, "officer1", "officer1pass")
    assert changes.version > before


def test_live_stream_is_admin_only_and_sends_events(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    assert client.get("/api/admin/live?limit=1").status_code == 403
    login(client, "admin", "adminpass")
    r = client.get("/api/admin/live?limit=1")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert "data: " in r.text and r.text.startswith("retry: ")


def test_dashboard_views_are_logged_once_per_ten_minutes_and_do_not_retrigger(client, seed_users, login):
    login(client, "admin", "adminpass")
    changes = client.app.state.changes
    client.get("/api/admin/dashboard")
    before = changes.version
    for _ in range(3):
        client.get("/api/admin/dashboard")
    assert changes.version == before  # viewing never makes dashboards refresh
    rows = [r for r in client.get("/api/audit?action=oversight_view").json()["items"] if r["detail"].get("view") == "dashboard"]
    assert len(rows) == 1
