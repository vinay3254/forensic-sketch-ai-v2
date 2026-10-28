"""Demo criminal-records database: fictional people (synthetic faces) with charge histories."""

import pytest
from PIL import Image
from sqlmodel import Session, select

from backend.models import RecordCharge, RecordPerson
from backend.records.seed import STATUSES, seed_records

FACES = [
    {"id": f"face{i:02d}_{'m' if i % 2 else 'f'}", "gender": "Male" if i % 2 else "Female", "age": "30-39"}
    for i in range(12)
]


@pytest.fixture
def seeded(app, client, settings):  # the client starts the app, which creates the tables
    faces = settings.storage_dir / "records" / "faces"
    faces.mkdir(parents=True)
    for f in FACES:
        Image.new("RGB", (40, 50), "grey").save(faces / f"{f['id']}_doc.jpg")
    with Session(app.state.engine) as s:
        seed_records(s, FACES)
        people = s.exec(select(RecordPerson)).all()
        return [(p.id, p.name, p.alias) for p in people]


@pytest.fixture
def officer(client, seed_users, login, seeded):
    login(client, "officer1", "officer1pass")
    return client


def test_seed_makes_one_person_per_face_each_with_charges(app, seeded):
    with Session(app.state.engine) as s:
        people = s.exec(select(RecordPerson)).all()
        charges = s.exec(select(RecordCharge)).all()
    assert len(people) == len(FACES)
    assert {c.person_id for c in charges} == {p.id for p in people}
    assert {c.status for c in charges} <= set(STATUSES)
    assert all(p.photo_path.startswith("records/faces/") for p in people)
    # gender follows the face
    assert {p.gender for p in people} == {"male", "female"}


def test_seed_is_deterministic_and_idempotent(app, seeded):
    with Session(app.state.engine) as s:
        assert seed_records(s, FACES) == 0  # already seeded: nothing added
        assert len(s.exec(select(RecordPerson)).all()) == len(FACES)


def test_records_need_login(client, seeded):
    assert client.get("/api/records").status_code == 401


def test_list_has_counts_totals_and_demo_notice(officer):
    r = officer.get("/api/records").json()
    assert r["total"] == len(FACES) and len(r["items"]) == len(FACES)
    assert r["demo"] is True and "fictional" in r["notice"].lower()
    item = r["items"][0]
    assert item["cases"] >= 1 and item["cases"] == item["convicted"] + item["pending"] + item["acquitted"]
    s = r["summary"]
    assert s["people"] == len(FACES) and s["cases"] == sum(i["cases"] for i in r["items"])


def test_search_by_name_and_alias(officer, seeded):
    _, name, _ = seeded[0]
    items = officer.get("/api/records", params={"q": name.split()[0]}).json()["items"]
    assert any(i["name"] == name for i in items)
    alias = next(a for _, _, a in seeded if a)
    assert any(i["alias"] == alias for i in officer.get("/api/records", params={"q": alias}).json()["items"])


def test_search_by_offence_and_filter_by_status(officer):
    all_items = officer.get("/api/records").json()["items"]
    offence = all_items[0]["latest_offence"]
    hits = officer.get("/api/records", params={"q": offence}).json()["items"]
    assert hits and all(h["cases"] >= 1 for h in hits)
    convicted = officer.get("/api/records", params={"status": "convicted"}).json()["items"]
    assert all(c["convicted"] >= 1 for c in convicted)


def test_search_is_audited(officer, login):
    officer.get("/api/records", params={"q": "theft", "status": "convicted"})
    login(officer, "admin", "adminpass")
    rows = officer.get("/api/audit?action=record_search").json()["items"]
    assert rows[0]["detail"] == {"q": "theft", "status": "convicted", "area": None, "results": rows[0]["detail"]["results"]}


def test_person_detail_lists_charges_newest_first_and_is_audited(officer, seeded, login):
    pid = seeded[0][0]
    d = officer.get(f"/api/records/{pid}").json()
    assert d["id"] == pid and d["charges"]
    dates = [c["date"] for c in d["charges"]]
    assert dates == sorted(dates, reverse=True)
    c = d["charges"][0]
    assert {"fir_no", "police_station", "section", "offence", "status", "date"} <= set(c)
    login(officer, "admin", "adminpass")
    rows = officer.get("/api/audit?action=record_view").json()["items"]
    assert rows[0]["detail"]["person_id"] == pid


def test_photo_is_served(officer, seeded):
    r = officer.get(f"/api/records/{seeded[0][0]}/photo")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_unknown_person_is_404(officer):
    assert officer.get("/api/records/9999").status_code == 404
