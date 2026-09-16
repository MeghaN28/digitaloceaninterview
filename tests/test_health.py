from app.database.mongodb import mongodb


def test_healthz(client):
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_when_db_reachable(client):
    resp = client.get("/readyz")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "ok"}


def test_readyz_when_db_unreachable(client, monkeypatch):
    monkeypatch.setattr(mongodb, "ping", lambda: False)

    resp = client.get("/readyz")

    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready", "database": "unavailable"}
