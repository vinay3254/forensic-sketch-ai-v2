"""Fixes for the minor findings deferred from the backend's final review."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from backend.ai.client import LiveAIClient
from backend.auth.ratelimit import LoginLimiter
from backend.config import Settings
from backend.errors import AppError
from backend.models import AuditLog, FaceVersion
from backend.tests.test_ai_client import _bad_request, fake_openai


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


def stored_pngs(settings):
    return sorted(p.name for p in settings.storage_dir.rglob("*.png"))


# 1. every error uses the {"error": {...}} shape


def test_unknown_route_uses_error_shape(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_wrong_method_uses_error_shape(client):
    r = client.delete("/api/cases")
    assert r.status_code == 405 and r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_unhandled_exception_uses_error_shape(app):
    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internals")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL" and "secret" not in r.text


# 2. refusal detection is not triggered by any mention of "content"


def test_unrelated_bad_request_mentioning_content_is_not_refusal(settings):
    def gen(**kw):
        raise _bad_request("Invalid type for 'content': expected a string")

    with pytest.raises(AppError) as e:
        LiveAIClient(settings, fake_openai(images=SimpleNamespace(generate=gen))).generate_image("p")
    assert e.value.code == "AI_UNAVAILABLE"


def test_content_policy_violation_is_refusal(settings):
    def gen(**kw):
        raise _bad_request("content_policy_violation")

    with pytest.raises(AppError) as e:
        LiveAIClient(settings, fake_openai(images=SimpleNamespace(generate=gen))).generate_image("p")
    assert e.value.code == "AI_REFUSED"


# 3. the hash covers who and where, and the chain head is reported


def test_tampered_username_breaks_chain(client, seed_users, login, app):
    login(client, "officer1", "officer1pass")
    with Session(app.state.engine) as s:
        row = s.get(AuditLog, 1)
        row.username = "someone-else"
        s.add(row)
        s.commit()
    login(client, "admin", "adminpass")
    assert client.get("/api/audit/verify").json() == {"ok": False, "rows": 2, "first_bad_id": 1}


def test_verify_reports_head_hash(client, seed_users, login, app):
    login(client, "admin", "adminpass")
    body = client.get("/api/audit/verify").json()
    with Session(app.state.engine) as s:
        last = s.get(AuditLog, body["rows"])
    assert body["ok"] and body["head_id"] == last.id and body["head_hash"] == last.hash


# 4. logout clears the cookie with its flags and revokes the token


def test_logout_revokes_token(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    token = client.cookies.get("session")
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("session", token)
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_logout_cookie_deletion_keeps_flags(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    header = client.post("/api/auth/logout").headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=strict" in header


# 5. unknown usernames cost a hash check; the limiter forgets old usernames


def test_unknown_username_still_checks_a_password_hash(client, seed_users, monkeypatch):
    from backend.auth import routes

    calls = []
    real = routes.verify_password
    monkeypatch.setattr(routes, "verify_password", lambda pw, h: calls.append(h) or real(pw, h))
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401 and len(calls) == 1


def test_limiter_drops_usernames_outside_window(monkeypatch):
    import backend.auth.ratelimit as rl

    now = [1000.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(rl, "SWEEP_EVERY", 3)
    limiter = LoginLimiter()
    limiter.fail("a")
    limiter.fail("b")
    now[0] += rl.WINDOW_SECONDS + 1
    limiter.fail("c")  # third failure triggers a sweep
    assert set(limiter._failures) == {"c"}


# 6. a database failure while saving a version removes the new image


def test_operational_error_leaves_no_orphan_png(client, case_id, app, settings, monkeypatch):
    client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    before = stored_pngs(settings)

    real_flush = Session.flush

    def failing_flush(self, *a, **kw):
        if any(isinstance(o, FaceVersion) for o in self.new):
            raise OperationalError("INSERT", {}, Exception("database is locked"))
        return real_flush(self, *a, **kw)

    monkeypatch.setattr(Session, "flush", failing_flush)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.cookies.update(client.cookies)
        r = c.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    assert r.status_code >= 500
    assert stored_pngs(settings) == before


# 7. bad image bytes are rejected before saving; a missing file is a 404


def test_corrupt_image_from_ai_is_rejected(client, case_id, app, settings):
    app.state.ai_client.generate_image = lambda prompt: b"not a png"
    r = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "AI_UNAVAILABLE"
    assert stored_pngs(settings) == []
    assert client.get(f"/api/cases/{case_id}/versions").json() == []


def test_missing_image_file_is_404(client, case_id, settings):
    v = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"}).json()
    for p in settings.storage_dir.rglob("*.png"):
        p.unlink()
    for url in (v["image_url"], f"/api/cases/{case_id}/versions/{v['id']}/export?style=photo"):
        r = client.get(url)
        assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


# 8. a replacement face is not called the first face


def test_replacement_generate_reply(client, case_id):
    client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    client.post(f"/api/cases/{case_id}/generate", json={"description": "female"})
    chat = client.get(f"/api/cases/{case_id}").json()["chat"]
    assert "first face" in chat[1]["content"] and "first face" not in chat[3]["content"]


# 9. audit_view records every filter used


def test_audit_view_records_all_filters(client, seed_users, login):
    login(client, "admin", "adminpass")
    client.get("/api/audit?user_id=2&since=2026-01-01T00:00:00Z&until=2026-12-31T00:00:00Z")
    row = client.get("/api/audit?action=audit_view").json()["items"][0]
    f = row["detail"]["filters"]
    assert f["user_id"] == 2 and f["since"].startswith("2026-01-01") and f["until"].startswith("2026-12-31")


# 10. a short JWT secret is refused at startup


def test_short_jwt_secret_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        Settings(jwt_secret="short", _env_file=None)
