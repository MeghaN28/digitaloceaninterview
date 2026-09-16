import mongomock
import pytest

from app.database.mongodb import MongoDB
from app.repositories.mongo_image_repository import MongoImageRepository


@pytest.fixture
def repo(monkeypatch):
    fake_db = MongoDB()
    fake_db.client = mongomock.MongoClient()
    fake_db.db = fake_db.client["test_db"]
    monkeypatch.setattr("app.repositories.mongo_image_repository.mongodb", fake_db)
    return MongoImageRepository()


def test_create_and_find_image(repo):
    repo.create_image(
        image_id="abc123",
        original_filename="photo.jpg",
        content_type="image/jpeg",
        created_at="2026-09-16T10:30:00Z",
    )

    found = repo.find_image("abc123")

    assert found["image_id"] == "abc123"
    assert found["original_filename"] == "photo.jpg"
    assert found["content_type"] == "image/jpeg"
    assert found["storage_key"] is None
    assert found["width"] is None
    assert found["height"] is None
    assert found["size_bytes"] is None
    assert "_id" not in found


def test_find_image_returns_none_when_missing(repo):
    assert repo.find_image("does-not-exist") is None
