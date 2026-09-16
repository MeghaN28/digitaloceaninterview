from datetime import datetime
from typing import Optional

from app.database.mongodb import mongodb


class MongoImageRepository:
    """MongoDB-backed repository. Only the operations needed to verify the
    database setup are implemented for now; the full image/thumbnail
    workflow will be wired up in a later phase."""

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
        }
        mongodb.images.insert_one(dict(doc))
        return doc

    def find_image(self, image_id: str) -> Optional[dict]:
        return mongodb.images.find_one({"image_id": image_id}, {"_id": 0})
