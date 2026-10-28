"""One-page printable case sheet."""

import io

import pytest
from PIL import Image

from backend.body import types


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "Chain snatching, Hebbal"}).json()["id"]


@pytest.fixture
def no_body_types(tmp_path, monkeypatch):
    monkeypatch.setattr(types, "ASSETS", tmp_path)


def generate(client, case_id):
    return client.post(f"/api/cases/{case_id}/generate", json={"description": "male, 30s, scar on left cheek"}).json()


def sheet(client, case_id, **params):
    return client.get(f"/api/cases/{case_id}/sheet", params=params)


def test_png_is_a4_landscape_at_300_dpi(client, case_id):
    generate(client, case_id)
    r = sheet(client, case_id)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(r.content)).size == (3508, 2480)
    assert "attachment" in r.headers["content-disposition"]


def test_pdf_is_valid(client, case_id):
    generate(client, case_id)
    r = sheet(client, case_id, format="pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"


def test_full_sheet_with_details_variants_figure_and_chart(client, case_id):
    v = generate(client, case_id)
    client.put(f"/api/cases/{case_id}/details", json={"height": "1.80 m", "build": "Heavy", "weapon": "a revolver"})
    client.post(f"/api/cases/{case_id}/versions/{v['id']}/variants", json={"kind": "cap"})
    client.post(f"/api/cases/{case_id}/body")
    assert sheet(client, case_id, version_id=v["id"]).status_code == 200


def test_renders_with_only_a_version(client, case_id, no_body_types):
    generate(client, case_id)
    assert sheet(client, case_id).status_code == 200


def test_bad_format_is_422(client, case_id):
    generate(client, case_id)
    assert sheet(client, case_id, format="docx").status_code == 422


def test_case_without_version_is_409(client, case_id):
    r = sheet(client, case_id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"


def test_version_of_other_case_is_404(client, case_id):
    v = generate(client, case_id)
    other = client.post("/api/cases", json={"title": "other"}).json()["id"]
    generate(client, other)
    assert sheet(client, other, version_id=v["id"]).status_code == 404


def test_other_officer_is_denied(client, case_id, login):
    generate(client, case_id)
    login(client, "officer2", "officer2pass")
    assert sheet(client, case_id).status_code == 403


def test_sheet_export_is_audited(client, case_id, login):
    v = generate(client, case_id)
    sheet(client, case_id, format="pdf")
    login(client, "admin", "adminpass")
    row = client.get(f"/api/audit?action=export&case_id={case_id}").json()["items"][0]
    assert row["version_id"] == v["id"] and row["detail"] == {"style": "sheet", "format": "pdf"}
