"""3D head from a sketch version, made by the separate GPU worker."""

import pytest

from backend.errors import AppError

GLB = b"glTF\x02\x00\x00\x00fake-mesh"


class FakeHead3D:
    def __init__(self):
        self.calls = []

    def make_head(self, photo_png: bytes) -> bytes:
        self.calls.append(photo_png)
        return GLB


@pytest.fixture
def head3d(app):
    app.state.head3d_client = FakeHead3D()
    return app.state.head3d_client


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


@pytest.fixture
def version(client, case_id):
    return client.post(f"/api/cases/{case_id}/generate", json={"description": "male, 30s"}).json()


def make(client, case_id, version_id):
    return client.post(f"/api/cases/{case_id}/versions/{version_id}/head")


def test_head_is_made_from_the_realistic_photo_made_first(client, case_id, version, head3d):
    assert version["photo_url"] is None
    r = make(client, case_id, version["id"])
    assert r.status_code == 200 and r.json()["version_no"] == 1
    photo = client.get(f"/api/cases/{case_id}/versions/{version['id']}/photo")
    assert photo.status_code == 200 and head3d.calls == [photo.content]


def test_mesh_is_served_as_glb(client, case_id, version, head3d):
    h = make(client, case_id, version["id"]).json()
    r = client.get(h["mesh_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "model/gltf-binary" and r.content == GLB


def test_list_is_newest_first(client, case_id, version, head3d):
    first = make(client, case_id, version["id"]).json()
    second = make(client, case_id, version["id"]).json()
    assert [h["id"] for h in client.get(f"/api/cases/{case_id}/heads").json()] == [second["id"], first["id"]]


def test_feature_off_is_503(client, case_id, version):
    r = make(client, case_id, version["id"])
    assert r.status_code == 503 and r.json()["error"]["code"] == "HEAD3D_OFF"


def test_worker_failure_is_503_audited_and_nothing_stored(app, client, case_id, version, head3d, login):
    def boom(photo_png):
        raise AppError("AI_UNAVAILABLE", "The 3D service did not respond. Try again.", 503)

    head3d.make_head = boom
    assert make(client, case_id, version["id"]).status_code == 503
    assert client.get(f"/api/cases/{case_id}/heads").json() == []
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=head_create&case_id={case_id}").json()["items"][0]
    assert row["detail"] == {"outcome": "AI_UNAVAILABLE"}


def test_success_is_audited(client, case_id, version, head3d, login):
    h = make(client, case_id, version["id"]).json()
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=head_create&case_id={case_id}").json()["items"][0]
    assert row["version_id"] == version["id"] and row["detail"] == {"outcome": "ok", "head_id": h["id"]}


def test_head_of_other_case_is_404(client, case_id, version, head3d):
    h = make(client, case_id, version["id"]).json()
    other = client.post("/api/cases", json={"title": "other"}).json()["id"]
    assert client.get(f"/api/cases/{other}/heads/{h['id']}/mesh").status_code == 404
    assert make(client, other, version["id"]).status_code == 404


def test_other_officer_is_denied(client, case_id, version, head3d, login):
    login(client, "officer2", "officer2pass")
    assert make(client, case_id, version["id"]).status_code == 403


def test_health_reports_head3d(client, head3d):
    assert client.get("/health").json()["head3d"] == "on"


def test_health_reports_head3d_off(client):
    assert client.get("/health").json()["head3d"] == "off"


def test_http_client_maps_errors_to_503():
    from backend.head3d.client import HttpHead3DClient

    with pytest.raises(AppError) as e:
        HttpHead3DClient("http://127.0.0.1:9").make_head(b"png")
    assert e.value.code == "AI_UNAVAILABLE"
