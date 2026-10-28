"""Five fixed body-type reference figures."""

import pytest
from PIL import Image

from backend.body import types


@pytest.fixture
def assets(tmp_path, monkeypatch):
    for key in ("slim", "heavy"):
        Image.new("L", (40, 80), 200).save(tmp_path / f"{key}.png")
    monkeypatch.setattr(types, "ASSETS", tmp_path)
    return tmp_path


@pytest.fixture
def logged_in(client, seed_users, login):
    login(client, "officer1", "officer1pass")


def test_list_has_only_present_files_in_fixed_order(client, assets, logged_in):
    assert client.get("/api/body-types").json() == [
        {"key": "slim", "label": "Slim", "image_url": "/api/body-types/slim/image"},
        {"key": "heavy", "label": "Heavy", "image_url": "/api/body-types/heavy/image"},
    ]


def test_image_is_served(client, assets, logged_in):
    r = client.get("/api/body-types/heavy/image")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"


@pytest.mark.parametrize("key", ["obese", "giant", "..%2Fsecret"])
def test_missing_or_unknown_type_is_404(client, assets, logged_in, key):
    assert client.get(f"/api/body-types/{key}/image").status_code == 404


def test_needs_login(client, assets):
    assert client.get("/api/body-types").status_code == 401


def test_all_five_types_are_defined():
    assert [k for k, _ in types.BODY_TYPES] == ["slim", "athletic", "overweight", "heavy", "obese"]
