def test_login_sets_httponly_cookie_and_me_returns_user(client, seed_users):
    r = client.post("/api/auth/login", json={"username": "officer1", "password": "officer1pass"})
    assert r.status_code == 200
    assert r.json()["role"] == "officer"
    cookie = r.headers["set-cookie"].lower()
    assert "session=" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/auth/me").json()["username"] == "officer1"


def test_wrong_password_is_401(client, seed_users):
    r = client.post("/api/auth/login", json={"username": "officer1", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_sixth_failed_login_is_rate_limited(client, seed_users):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "officer1", "password": "x"})
    r = client.post("/api/auth/login", json={"username": "officer1", "password": "officer1pass"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


def test_me_without_cookie_is_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_tampered_cookie_is_401_not_500(client, seed_users):
    client.cookies.set("session", "not.a.jwt")
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_expired_token_is_401(client, seed_users, settings):
    from backend.auth.security import create_token

    expired = settings.model_copy(update={"jwt_expiry_hours": -1})
    client.cookies.set("session", create_token(1, "officer", expired))
    assert client.get("/api/auth/me").status_code == 401


def test_validation_error_uses_error_shape(client):
    r = client.post("/api/auth/login", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION"


def test_logout_clears_session(client, seed_users):
    client.post("/api/auth/login", json={"username": "officer1", "password": "officer1pass"})
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_vinay3254_can_log_in_as_officer(client, seed_users):
    r = client.post("/api/auth/login", json={"username": "vinay3254", "password": "7767"})
    assert r.status_code == 200 and r.json()["role"] == "officer"
