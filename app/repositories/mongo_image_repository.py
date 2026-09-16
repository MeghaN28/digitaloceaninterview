from datetime import datetime
from typing import Optional

from pymongo.errors import DuplicateKeyError

from app.core.metrics import db_metrics, timed
from app.database.mongodb import mongodb

from .exceptions import DuplicateThumbnailError


class MongoImageRepository:
    """MongoDB-backed repository.

    Images and thumbnails are separate collections (matching the schema/
    indexes set up in app/database/mongodb.py), so get_image composes the
    nested "thumbnails" list controllers.py/schemas.py expect by querying
    the thumbnails collection separately - the caller doesn't need to know
    storage is split across two collections.
    """

    def create_image(
        self,
        image_id: str,
        original_filename: str,
        content_type: str,
        storage_key: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        size_bytes: Optional[int] = None,
        created_at: Optional[str] = None,
        content_hash: Optional[str] = None,
    ) -> dict:
        doc = {
            "image_id": image_id,
            "original_filename": original_filename,
            "storage_key": storage_key,
            "content_type": content_type,
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
            "created_at": created_at or datetime.utcnow().isoformat() + "Z",
            "content_hash": content_hash,
        }
        with timed(db_metrics, "mongo_repo.create_image"):
            mongodb.images.insert_one(dict(doc))
        return doc

    def find_image(self, image_id: str) -> Optional[dict]:
        with timed(db_metrics, "mongo_repo.find_image"):
            return mongodb.images.find_one({"image_id": image_id}, {"_id": 0})

    def find_by_content_hash(self, content_hash: str) -> Optional[dict]:
        with timed(db_metrics, "mongo_repo.find_by_content_hash"):
            return mongodb.images.find_one({"content_hash": content_hash}, {"_id": 0})

    # --- interface expected by app/api/controllers.py (same shape as
    # LocalImageRepository) so the two repositories are interchangeable ---

    def save_image(self, image_id: str, filename: str, content_type: str, width: int, height: int, size_bytes: int, created_at: str, content_hash: Optional[str] = None) -> None:
        self.create_image(
            image_id=image_id,
            original_filename=filename,
            content_type=content_type,
            width=width,
            height=height,
            size_bytes=size_bytes,
            created_at=created_at,
            content_hash=content_hash,
        )

    def get_image(self, image_id: str) -> Optional[dict]:
        rec = self.find_image(image_id)
        if rec is None:
            return None
        with timed(db_metrics, "mongo_repo.get_image_thumbnails"):
            rec["thumbnails"] = list(mongodb.thumbnails.find({"image_id": image_id}, {"_id": 0}))
        return rec

    def add_thumbnail(self, image_id: str, thumbnail_record: dict) -> None:
        with timed(db_metrics, "mongo_repo.add_thumbnail"):
            if self.find_image(image_id) is None:
                raise KeyError("image not found")

            preset = thumbnail_record.get("preset")
            doc = {**thumbnail_record, "image_id": image_id}

            # Optimistic pre-check (works even where the unique index isn't
            # set up, e.g. mongomock in tests) plus the real unique partial
            # index (image_id, preset) as the authoritative guard against a
            # genuine race under concurrent real-Mongo writes.
            if preset is not None and mongodb.thumbnails.find_one({"image_id": image_id, "preset": preset}):
                raise DuplicateThumbnailError(f"a '{preset}' thumbnail already exists for image {image_id}")

            try:
                mongodb.thumbnails.insert_one(doc)
            except DuplicateKeyError:
                raise DuplicateThumbnailError(f"a '{preset}' thumbnail already exists for image {image_id}")
