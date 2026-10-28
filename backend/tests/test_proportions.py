"""Proportion sliders: the sketch is reshaped locally (eyes, nose, mouth, face length, jaw)
around landmarks from the face parser, with no AI call."""

import io

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.face.proportions import Adjust, landmarks, warp
from backend.tests.test_regions import FakeParser, face_map

EYE = (205, 215)  # left eye in face_map: under the middle of the left brow, between brow and nose


def sketch(draw) -> bytes:
    img = Image.new("L", (512, 512), 255)
    draw(ImageDraw.Draw(img))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def dark(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("L")) < 128


def eye_disc(d):
    d.ellipse((EYE[0] - 10, EYE[1] - 10, EYE[0] + 10, EYE[1] + 10), fill=0)


def test_landmarks_from_parser_map():
    lm = landmarks(face_map())
    (lx, ly), (rx, _) = lm.eyes
    assert abs(lx - 205) <= 3 and abs(ly - 215) <= 4 and abs(rx - 307) <= 3
    assert lm.chin == 419 and lm.face_left == 140 and lm.face_right == 371
    assert lm.nose == (226, 240, 285, 299)


def test_no_face_means_no_landmarks():
    assert landmarks(np.zeros((512, 512), np.uint8)) is None


def test_zero_adjustment_changes_nothing():
    src = sketch(eye_disc)
    out = warp(src, landmarks(face_map()), Adjust())
    assert (dark(out) == dark(src)).all()


def test_bigger_eyes():
    src = sketch(eye_disc)
    out = warp(src, landmarks(face_map()), Adjust(eye_size=1))
    assert dark(out).sum() > dark(src).sum() * 1.2


def test_smaller_eyes():
    src = sketch(eye_disc)
    out = warp(src, landmarks(face_map()), Adjust(eye_size=-1))
    assert dark(out).sum() < dark(src).sum() * 0.85


def test_wider_eye_spacing_moves_the_left_eye_outwards():
    out = dark(warp(sketch(eye_disc), landmarks(face_map()), Adjust(eye_spacing=1)))
    assert np.argwhere(out)[:, 1].mean() < EYE[0] - 3


def test_longer_face_moves_the_chin_down():
    src = sketch(lambda d: d.line((200, 410, 312, 410), fill=0, width=3))
    out = dark(warp(src, landmarks(face_map()), Adjust(face_length=1)))
    assert np.argwhere(out)[:, 0].mean() > 418


def test_wider_jaw_spreads_the_jaw_line():
    src = sketch(lambda d: (d.line((160, 380, 160, 400), fill=0, width=3), d.line((352, 380, 352, 400), fill=0, width=3)))
    out = np.argwhere(dark(warp(src, landmarks(face_map()), Adjust(jaw_width=1))))[:, 1]
    assert out.min() < 155 and out.max() > 357


def test_wider_nose():
    src = sketch(lambda d: d.rectangle((246, 260, 266, 290), fill=0))
    out = dark(warp(src, landmarks(face_map()), Adjust(nose_width=1)))
    assert out.sum() > dark(src).sum() * 1.15


def test_longer_nose_moves_its_tip_down():
    src = sketch(lambda d: d.line((236, 298, 276, 298), fill=0, width=3))
    out = dark(warp(src, landmarks(face_map()), Adjust(nose_length=1)))
    assert np.argwhere(out)[:, 0].mean() > 302


def test_adjust_values_are_bounded():
    with pytest.raises(ValueError):
        Adjust(eye_size=1.5)


def test_describe_lists_only_changed_sliders():
    assert Adjust(eye_size=0.5, face_length=-0.25).describe() == "eye size +50%, face length -25%"
    assert Adjust().is_zero()


# --- API -------------------------------------------------------------------------------------


@pytest.fixture
def case_v1(app, client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    v = client.post(f"/api/cases/{cid}/generate", json={"description": "male"}).json()
    app.state.face_parser = FakeParser(face_map())
    return cid, v


def test_preview_returns_png_without_new_version(client, case_v1):
    cid, v = case_v1
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/proportions/preview", json={"eye_size": 0.5})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert len(client.get(f"/api/cases/{cid}/versions").json()) == 1


def test_apply_creates_an_audited_version(client, case_v1, login):
    cid, v = case_v1
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/proportions", json={"eye_size": 0.5, "face_length": -0.25})
    assert r.status_code == 200, r.text
    nv = r.json()
    assert nv["version_no"] == 2 and nv["kind"] == "adjust" and nv["attributes"] == v["attributes"]
    assert nv["instruction"] == "Proportions: eye size +50%, face length -25%"
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=proportion_adjust&case_id={cid}").json()["items"]
    assert rows[0]["version_id"] == nv["id"] and rows[0]["detail"]["eye_size"] == 0.5


def test_apply_with_nothing_changed_is_rejected(client, case_v1):
    cid, v = case_v1
    assert client.post(f"/api/cases/{cid}/versions/{v['id']}/proportions", json={}).status_code == 422


def test_out_of_range_value_is_rejected(client, case_v1):
    cid, v = case_v1
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/proportions/preview", json={"eye_size": 3})
    assert r.status_code == 422


def test_without_face_parser_the_sliders_are_off(app, client, case_v1):
    cid, v = case_v1
    app.state.face_parser = None
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/proportions/preview", json={"eye_size": 0.5})
    assert r.status_code == 503 and r.json()["error"]["code"] == "PROPORTIONS_OFF"


def test_face_not_found_is_reported(app, client, case_v1):
    cid, v = case_v1
    app.state.face_parser = FakeParser(np.zeros((512, 512), np.uint8))
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/proportions/preview", json={"eye_size": 0.5})
    assert r.status_code == 422 and r.json()["error"]["code"] == "FACE_NOT_FOUND"


def test_version_of_another_case_is_not_found(client, case_v1):
    cid, v = case_v1
    other = client.post("/api/cases", json={"title": "u"}).json()["id"]
    r = client.post(f"/api/cases/{other}/versions/{v['id']}/proportions/preview", json={"eye_size": 0.5})
    assert r.status_code == 404
