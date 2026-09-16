import mongomock
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.database.mongodb import mongodb


@pytest.fixture
def client(monkeypatch, tmp_path):
    def fake_connect():
        mongodb.client = mongomock.MongoClient()
        mongodb.db = mongodb.client["test_db"]

    monkeypatch.setattr(mongodb, "connect", fake_connect)
    monkeypatch.setattr(mongodb, "create_indexes", lambda: None)
    monkeypatch.setattr(mongodb, "close", lambda: None)

    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "DB_FILE", str(tmp_path / "db.json"))
    monkeypatch.setattr(settings, "THUMBNAILS_DIR", str(tmp_path / "thumbnails"))

    main_module.rate_limiter.reset()
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.rate_limiter.reset()
