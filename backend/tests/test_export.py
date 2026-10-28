import io

from PIL import Image


def make_version(client, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    v = client.post(f"/api/cases/{cid}/generate", json={"description": "male"}).json()
    return cid, v


def test_photo_export_is_2048_long_side_plus_footer(client, seed_users, login):
    cid, v = make_version(client, login)
    r = client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=photo")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "_v1_photo.png" in r.headers["content-disposition"]
    img = Image.open(io.BytesIO(r.content))
    assert img.format == "PNG" and img.width == 1365 and img.height > 2048  # 1024x1536 source


def test_sketch_export_is_grayscale(client, seed_users, login):
    cid, v = make_version(client, login)
    img = Image.open(io.BytesIO(client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=sketch").content))
    assert img.mode == "L"


def test_export_is_audited_with_style(client, seed_users, login):
    cid, v = make_version(client, login)
    client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=sketch")
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=export&case_id={cid}").json()["items"]
    assert rows[0]["detail"] == {"style": "sketch"}


def test_bad_style_is_422(client, seed_users, login):
    cid, v = make_version(client, login)
    assert client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=oil").status_code == 422


def test_other_officer_cannot_export(client, seed_users, login):
    cid, v = make_version(client, login)
    login(client, "officer2", "officer2pass")
    assert client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=photo").status_code == 403
