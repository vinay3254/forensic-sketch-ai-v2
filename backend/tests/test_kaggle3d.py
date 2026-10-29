"""Kaggle 3D: a background job draws side and back views, gets a 3D shape from a Kaggle GPU, paints it with
the drawings and saves it as the case's body model. Kaggle and Blender are replaced by fakes here."""

import time

import pytest

from backend.ai.prompts import VIEW_PROMPTS
from backend.tests.test_body_model import GLB


class Shapes:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def make_shape(self, views, stage):
        stage("kaggle")
        if self.fail:
            raise RuntimeError(self.fail)
        self.calls.append(views)
        return b"SHAPE"


class Painter:
    def __init__(self):
        self.calls = []

    def paint(self, shape, views, height_cm):
        self.calls.append((shape, views, height_cm))
        return GLB, b"BLEND", "painted from front, side, back"


@pytest.fixture
def setup(client, app, seed_users, login):
    login(client, "officer1", "officer1pass")
    case_id = client.post("/api/cases", json={"title": "Kaggle 3D"}).json()["id"]
    source = client.post(f"/api/cases/{case_id}/body").json()
    shapes, painter = Shapes(), Painter()
    app.state.kaggle_shapes, app.state.view_painter = shapes, painter
    return case_id, source, shapes, painter


def wait(client, case_id):
    for _ in range(100):
        job = client.get(f"/api/cases/{case_id}/figure/kaggle").json()
        if job and job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_job_builds_and_saves_a_painted_model(client, setup):
    case, source, shapes, painter = setup
    r = client.post(f"/api/cases/{case}/figure/kaggle", json={"body_id": source["id"]})
    assert r.status_code == 202, r.text
    job = wait(client, case)
    assert job["status"] == "done", job
    assert set(shapes.calls[0]) == {"front", "side", "back"}
    assert shapes.calls[0]["front"] == client.get(source["image_url"]).content
    assert painter.calls[0][0] == b"SHAPE" and painter.calls[0][2] == 172
    model = client.get(f"/api/cases/{case}/figure/reconstruction").json()
    assert model["id"] == job["model_id"] and model["engine"].startswith("Hunyuan3D-2")
    assert client.get(model["mesh_url"]).content == GLB and client.get(model["blend_url"]).content == b"BLEND"


def test_side_and_back_come_from_the_image_model(client, app, setup):
    case, _, _, _ = setup
    prompts = []
    real = app.state.ai_client.edit_image
    app.state.ai_client.edit_image = lambda image, prompt: (prompts.append(prompt), real(image, prompt))[1]
    client.post(f"/api/cases/{case}/figure/kaggle", json={})
    wait(client, case)
    assert sorted(prompts) == sorted(VIEW_PROMPTS.values())


def test_failure_is_reported_and_keeps_the_old_model(client, app, setup):
    case, _, _, _ = setup
    client.post(f"/api/cases/{case}/figure/kaggle", json={})
    first = wait(client, case)
    app.state.kaggle_shapes = Shapes(fail="Kaggle GPU quota used up")
    client.post(f"/api/cases/{case}/figure/kaggle", json={})
    job = wait(client, case)
    assert job["status"] == "failed" and "quota" in job["error"]
    assert client.get(f"/api/cases/{case}/figure/reconstruction").json()["id"] == first["model_id"]


def test_start_and_finish_are_audited(client, setup, login):
    case, _, _, _ = setup
    client.post(f"/api/cases/{case}/figure/kaggle", json={})
    wait(client, case)
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=body_kaggle&case_id={case}").json()["items"]
    assert [r["detail"]["outcome"] for r in rows] == ["ok", "started"]


def test_off_without_kaggle(client, app, setup):
    case, _, _, _ = setup
    app.state.kaggle_shapes = None
    r = client.post(f"/api/cases/{case}/figure/kaggle", json={})
    assert r.status_code == 503 and r.json()["error"]["code"] == "KAGGLE_OFF"


def test_needs_a_full_body_image(client, app, seed_users, login):
    login(client, "officer1", "officer1pass")
    case = client.post("/api/cases", json={"title": "empty"}).json()["id"]
    app.state.kaggle_shapes, app.state.view_painter = Shapes(), Painter()
    assert client.post(f"/api/cases/{case}/figure/kaggle", json={}).status_code == 404


def test_one_job_at_a_time_per_case(client, app, setup):
    case, _, _, _ = setup

    class Slow(Shapes):
        def make_shape(self, views, stage):
            time.sleep(0.5)
            return super().make_shape(views, stage)

    app.state.kaggle_shapes = Slow()
    assert client.post(f"/api/cases/{case}/figure/kaggle", json={}).status_code == 202
    assert client.post(f"/api/cases/{case}/figure/kaggle", json={}).status_code == 409
    wait(client, case)
