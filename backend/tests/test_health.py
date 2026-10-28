def test_health_reports_ok_and_mock_mode(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok", "ai_mode": "mock", "head3d": "off"}
