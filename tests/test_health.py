import mongomock
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.database.mongodb import mongodb


@pytest.fixture
def client(monkeypatch):
    def fake_connect():
        mongodb.client = mongomock.MongoClient()
        mongodb.db = mongodb.client["test_db"]

    monkeypatch.setattr(mongodb, "connect", fake_connect)
    monkeypatch.setattr(mongodb, "create_indexes", lambda: None)
    monkeypatch.setattr(mongodb, "close", lambda: None)

    with TestClient(main_module.app) as test_client:
        yield test_client


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
