"""Integration tests that hit a real MongoDB instance.

These are NOT run by a plain `pytest` invocation against the DigitalOcean
cluster by accident: they only execute when MONGODB_URI is present in the
environment (e.g. exported locally, or injected by CI as a secret), and are
skipped otherwise. Run explicitly with:

    MONGODB_URI=... MONGODB_DATABASE=... pytest -m integration
"""
import os
import uuid

import pytest

from app.database.mongodb import MongoDB
from app.repositories.mongo_image_repository import MongoImageRepository

pytestmark = pytest.mark.integration

MONGODB_URI = os.environ.get("MONGODB_URI")

requires_real_mongodb = pytest.mark.skipif(
    not MONGODB_URI, reason="MONGODB_URI not set; skipping real MongoDB integration test"
)


@pytest.fixture
def real_mongodb():
    db = MongoDB()
    db.connect()
    db.create_indexes()
    yield db
    db.close()


@requires_real_mongodb
def test_can_ping_real_mongodb(real_mongodb):
    assert real_mongodb.ping() is True


@requires_real_mongodb
def test_can_create_and_find_image_in_real_mongodb(real_mongodb, monkeypatch):
    monkeypatch.setattr("app.repositories.mongo_image_repository.mongodb", real_mongodb)
    repo = MongoImageRepository()
    image_id = f"itest-{uuid.uuid4().hex}"

    try:
        repo.create_image(
            image_id=image_id,
            original_filename="integration.jpg",
            content_type="image/jpeg",
            created_at="2026-09-16T10:30:00Z",
        )
        found = repo.find_image(image_id)
        assert found["image_id"] == image_id
    finally:
        real_mongodb.images.delete_one({"image_id": image_id})
