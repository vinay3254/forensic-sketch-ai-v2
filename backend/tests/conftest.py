import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        jwt_secret="test",
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
