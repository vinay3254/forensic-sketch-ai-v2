"""Suspect matching: a sketch version (its realistic photo when there is one) against the records' mugshots."""

import hashlib
import io

import numpy as np
import pytest
from PIL import Image
from sqlmodel import Session, select

from backend.matching.faces import NoFace
from backend.models import FaceVersion, RecordPerson
from backend.records.seed import seed_records

FACES = [{"id": f"face{i:02d}_m", "gender": "Male", "age": "30-39"} for i in range(8)]


def jpeg(shade: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 50), (shade, shade, shade)).save(buf, "JPEG")
    return buf.getvalue()


class FakeEmbedder:
    """Same bytes -> same fingerprint; a blank (white) picture has no face."""

    def __init__(self):
        self.calls = 0

    def embed(self, image: bytes) -> np.ndarray:
        self.calls += 1
        if Image.open(io.BytesIO(image)).convert("L").getpixel((0, 0)) > 250:
            raise NoFace("no face")
        v = np.frombuffer(hashlib.sha256(image).digest(), np.uint8).astype(np.float32) - 127.5
        return v / np.linalg.norm(v)


@pytest.fixture
def world(app, client, settings, seed_users, login):
    faces = settings.storage_dir / "records" / "faces"
    faces.mkdir(parents=True)
    for i, f in enumerate(FACES):
        (faces / f"{f['id']}_doc.jpg").write_bytes(jpeg(20 + i * 20))
    with Session(app.state.engine) as s:
        seed_records(s, FACES)
    app.state.face_matcher = FakeEmbedder()
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "Bag theft"}).json()["id"]
    v = client.post(f"/api/cases/{cid}/generate", json={"description": "male"}).json()
    return cid, v


def use_as_sketch(app, settings, vid, data: bytes):
    with Session(app.state.engine) as s:
        v = s.get(FaceVersion, vid)
        (settings.storage_dir / v.image_path).write_bytes(data)


def person_with(app, i):
    with Session(app.state.engine) as s:
        return s.exec(select(RecordPerson).where(RecordPerson.source == f"FLUXSynID {FACES[i]['id']}")).one()


def test_the_matching_record_comes_first_and_is_strong(client, app, settings, world):
    cid, v = world
    use_as_sketch(app, settings, v["id"], jpeg(20 + 3 * 20))  # the same picture as record 3's mugshot
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/matches")
    assert r.status_code == 200, r.text
    d = r.json()
    top = d["results"][0]
    assert top["id"] == person_with(app, 3).id and top["band"] == "strong" and top["score"] > 0.99
    assert len(d["results"]) == 5 and d["query"] == "sketch"
    assert [x["score"] for x in d["results"]] == sorted((x["score"] for x in d["results"]), reverse=True)
    assert "lead" in d["notice"].lower()


def test_photo_is_used_when_there_is_one(client, app, settings, world):
    cid, v = world
    with Session(app.state.engine) as s:
        fv = s.get(FaceVersion, v["id"])
        fv.photo_path = f"cases/{cid}/photo-test.png"
        (settings.storage_dir / fv.photo_path).write_bytes(jpeg(20 + 5 * 20))
        s.add(fv)
        s.commit()
    d = client.post(f"/api/cases/{cid}/versions/{v['id']}/matches").json()
    assert d["query"] == "photo" and d["results"][0]["id"] == person_with(app, 5).id


def test_record_fingerprints_are_computed_once(client, app, settings, world):
    cid, v = world
    use_as_sketch(app, settings, v["id"], jpeg(30))
    client.post(f"/api/cases/{cid}/versions/{v['id']}/matches")
    first = app.state.face_matcher.calls
    client.post(f"/api/cases/{cid}/versions/{v['id']}/matches")
    assert app.state.face_matcher.calls == first + 1  # only the query again


def test_search_is_audited_with_the_scores(client, app, settings, world, login):
    cid, v = world
    use_as_sketch(app, settings, v["id"], jpeg(20))
    client.post(f"/api/cases/{cid}/versions/{v['id']}/matches")
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=suspect_match&case_id={cid}").json()["items"][0]
    assert row["version_id"] == v["id"] and row["detail"]["query"] == "sketch"
    assert len(row["detail"]["top"]) == 5 and {"person_id", "score"} <= set(row["detail"]["top"][0])


def test_no_face_in_the_picture_is_422(client, app, settings, world):
    cid, v = world
    use_as_sketch(app, settings, v["id"], jpeg(255))
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/matches")
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_FACE"


def test_off_without_the_models(client, app, world):
    cid, v = world
    app.state.face_matcher = None
    r = client.post(f"/api/cases/{cid}/versions/{v['id']}/matches")
    assert r.status_code == 503 and r.json()["error"]["code"] == "MATCHING_OFF"


def test_version_of_another_case_is_404(client, world):
    cid, v = world
    other = client.post("/api/cases", json={"title": "x"}).json()["id"]
    assert client.post(f"/api/cases/{other}/versions/{v['id']}/matches").status_code == 404
