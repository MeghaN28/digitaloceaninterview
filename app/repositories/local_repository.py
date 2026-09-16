import json
import threading
from typing import Optional
from datetime import datetime
from pathlib import Path

from .base import ImageRecord, ImageRepository


class LocalImageRepository:
    def __init__(self, db_file: str):
        self.db_file = Path(db_file)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.db_file.exists():
            self._write_db({})

    def _read_db(self):
        with self._lock:
            with self.db_file.open("r", encoding="utf-8") as f:
                return json.load(f)

    def _write_db(self, data):
        with self._lock:
            with self.db_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def save_image(self, image_id: str, filename: str, content_type: str, width: int, height: int, size_bytes: int, created_at: str) -> None:
        db = self._read_db()
        db[image_id] = {
            "image_id": image_id,
            "original_filename": filename,
            "content_type": content_type,
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
            "created_at": created_at,
            "thumbnails": [],
        }
        self._write_db(db)

    def get_image(self, image_id: str) -> Optional[ImageRecord]:
        db = self._read_db()
        return db.get(image_id)

    def add_thumbnail(self, image_id: str, thumbnail_record: dict) -> None:
        db = self._read_db()
        rec = db.get(image_id)
        if not rec:
            raise KeyError("image not found")
        rec.setdefault("thumbnails", [])
        rec["thumbnails"].append(thumbnail_record)
        db[image_id] = rec
        self._write_db(db)
