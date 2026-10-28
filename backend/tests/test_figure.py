"""Blender figure: settings per case, prompt-driven changes, live model, save to the case sheet."""

import pytest

from backend.ai.mock import MockAIClient
from backend.errors import AppError
from backend.figure.params import FigureParams, apply_changes, defaults_for

GLB = b"glTF\x02\x00\x00\x00fake"
PNG = b"\x89PNG\r\n\x1a\nfake"


class FakeWorker:
    def __init__(self):
        self.calls = []

    def glb(self, p: FigureParams) -> bytes:
        self.calls.append(("glb", p))
        return GLB

    def png(self, p: FigureParams) -> bytes:
        self.calls.append(("png", p))
        from PIL import Image
        import io

        buf = io.BytesIO()
        Image.new("RGBA", (52, 100), (0, 0, 0, 0)).save(buf, "PNG")
        return buf.getvalue()

    def blend(self, p: FigureParams) -> bytes:
        self.calls.append(("blend", p))
        return b"BLENDER-v502fake"


@pytest.fixture
def worker(app):
    app.state.figure_worker = FakeWorker()
    return app.state.figure_worker


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


def test_defaults_come_from_case_details_and_sketch():
    p = defaults_for({"height": "about 5 ft 4", "build": "Heavy", "clothing": "blue kurta and jeans"}, {"gender": "female", "age_range": "late twenties"})
    assert round(p.height_cm) == 163 and p.build == pytest.approx(0.75) and p.gender == 1.0
    assert p.top == "kurta" and p.bottom == "jeans" and p.age == pytest.approx(28)


@pytest.mark.parametrize("height,cm", [("1.80 m", 180), ("180cm", 180), ("6 feet", 183), ("5'10\"", 178), ("tall", 172)])
def test_height_text_is_read_in_any_unit(height, cm):
    assert round(defaults_for({"height": height}, {}).height_cm) == cm


def test_changes_are_clamped_and_unknown_clothes_ignored():
    p = apply_changes(FigureParams(), {"height_cm": 400, "build": -2, "top": "spacesuit", "bottom": "shorts"})
    assert p.height_cm == 220 and p.build == 0 and p.top == FigureParams().top and p.bottom == "shorts"


def test_mock_prompt_understands_common_requests():
    ai = MockAIClient()
    base = FigureParams()
    e = ai.figure_edit("make him heavier and taller, about 185 cm, put a jacket and jeans on him", base)
    p = apply_changes(base, e.changes)
    assert p.build > base.build and p.height_cm == 185 and p.top == "jacket" and p.bottom == "jeans" and e.reply


def test_get_figure_starts_from_defaults(client, case_id):
    client.put(f"/api/cases/{case_id}/details", json={"height": "180 cm", "build": "Slim"})
    f = client.get(f"/api/cases/{case_id}/figure").json()
    assert f["params"]["height_cm"] == 180 and f["params"]["build"] == pytest.approx(0.1)
    assert f["model_url"].endswith("/figure/model.glb")


def test_put_saves_params_and_audits(client, case_id, login):
    r = client.put(f"/api/cases/{case_id}/figure", json={"height_cm": 190, "top": "hoodie"})
    assert r.status_code == 200 and r.json()["params"]["height_cm"] == 190
    assert client.get(f"/api/cases/{case_id}/figure").json()["params"]["top"] == "hoodie"
    login(client, "admin", "adminpass")
    assert client.get(f"/api/audit?action=figure_update&case_id={case_id}").json()["items"]


def test_put_rejects_bad_values(client, case_id):
    assert client.put(f"/api/cases/{case_id}/figure", json={"height_cm": 30}).status_code == 422
    assert client.put(f"/api/cases/{case_id}/figure", json={"top": "spacesuit"}).status_code == 422


def test_prompt_changes_the_figure(client, case_id):
    r = client.post(f"/api/cases/{case_id}/figure/prompt", json={"text": "make him heavier, 185 cm, jacket"})
    assert r.status_code == 200
    body = r.json()
    assert body["params"]["height_cm"] == 185 and body["params"]["top"] == "jacket" and body["reply"]
    assert client.get(f"/api/cases/{case_id}/figure").json()["params"]["height_cm"] == 185


def test_model_is_built_by_the_worker(client, case_id, worker):
    r = client.get(f"/api/cases/{case_id}/figure/model.glb")
    assert r.status_code == 200 and r.content == GLB and r.headers["content-type"] == "model/gltf-binary"


def test_preview_builds_unsaved_params(client, case_id, worker):
    r = client.post(f"/api/cases/{case_id}/figure/preview.glb", json={"height_cm": 199})
    assert r.status_code == 200 and worker.calls[-1][1].height_cm == 199
    assert client.get(f"/api/cases/{case_id}/figure").json()["params"]["height_cm"] != 199


def test_save_puts_the_render_on_the_case_sheet(client, case_id, worker, login):
    r = client.post(f"/api/cases/{case_id}/figure/save")
    assert r.status_code == 200
    body = client.get(f"/api/cases/{case_id}/body").json()
    assert body["image_url"] and client.get(body["image_url"]).status_code == 200
    login(client, "admin", "adminpass")
    assert client.get(f"/api/audit?action=figure_save&case_id={case_id}").json()["items"]


def test_blend_download(client, case_id, worker):
    r = client.get(f"/api/cases/{case_id}/figure.blend")
    assert r.status_code == 200 and r.content.startswith(b"BLENDER") and "attachment" in r.headers["content-disposition"]


def test_worker_off_is_503(client, case_id):
    r = client.get(f"/api/cases/{case_id}/figure/model.glb")
    assert r.status_code == 503 and r.json()["error"]["code"] == "FIGURE_OFF"


def test_worker_failure_is_503(app, client, case_id, worker):
    def boom(p):
        raise AppError("AI_UNAVAILABLE", "The Blender worker did not respond. Try again.", 503)

    worker.glb = boom
    assert client.get(f"/api/cases/{case_id}/figure/model.glb").status_code == 503


def test_other_officer_is_denied(client, case_id, login):
    login(client, "officer2", "officer2pass")
    assert client.get(f"/api/cases/{case_id}/figure").status_code == 403
