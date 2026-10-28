import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        jwt_secret="test-secret-at-least-32-bytes-long!!",
        cookie_secure=False,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_dir=tmp_path / "storage",
        ai_mock=True,
        _env_file=None,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seed_users(app, client):
    from sqlmodel import Session

    from backend.seed import seed_users as _seed

    with Session(app.state.engine) as s:
        _seed(s)


@pytest.fixture
def login():
    def _login(client, username, password):
        client.cookies.clear()
        r = client.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        return r.json()

    return _login
