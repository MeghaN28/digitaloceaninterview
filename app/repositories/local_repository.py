import json
import threading
from typing import Optional
from pathlib import Path

from app.core.metrics import db_metrics, timed

from .base import ImageRecord, ImageRepository
from .exceptions import DuplicateThumbnailError

__all__ = ["DuplicateThumbnailError", "LocalImageRepository"]


class LocalImageRepository:
    """JSON-file-backed repository.

    A single process-wide lock guards the entire read-modify-write cycle of
    every operation (not just the individual file read or write), so
    concurrent requests can't interleave and corrupt the file or silently
    drop each other's updates. The lock is a class attribute - not set in
    __init__ - because controllers.py builds a fresh LocalImageRepository
    per request (see get_repo); an instance-level lock would give every
    request its own lock and provide no real mutual exclusion at all.
    """

    _lock = threading.Lock()

    def __init__(self, db_file: str):
        self.db_file = Path(db_file)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_file.exists():
            with self._lock:
                if not self.db_file.exists():
                    self._write_db_locked({})

    def _read_db_locked(self):
        with self.db_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write_db_locked(self, data):
        with self.db_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_image(self, image_id: str, filename: str, content_type: str, width: int, height: int, size_bytes: int, created_at: str) -> None:
        # timed() wraps the lock acquisition too, on purpose - time spent
        # waiting for the lock under concurrent load IS the latency we want
        # to see here, not just the file I/O once we have it.
        with timed(db_metrics, "local_repo.save_image"):
            with self._lock:
                db = self._read_db_locked()
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
                self._write_db_locked(db)

    def get_image(self, image_id: str) -> Optional[ImageRecord]:
        with timed(db_metrics, "local_repo.get_image"):
            with self._lock:
                db = self._read_db_locked()
            return db.get(image_id)

    def add_thumbnail(self, image_id: str, thumbnail_record: dict) -> None:
        # Checked and appended inside the same locked section as the
        # read-modify-write cycle (not as a separate pre-check) so two
        # concurrent requests for the same (image_id, preset) can't both
        # pass the check and both append - the same class of race already
        # fixed for save_image/get_image above.
        with timed(db_metrics, "local_repo.add_thumbnail"):
            with self._lock:
                db = self._read_db_locked()
                rec = db.get(image_id)
                if not rec:
                    raise KeyError("image not found")
                rec.setdefault("thumbnails", [])

                preset = thumbnail_record.get("preset")
                if preset is not None and any(t.get("preset") == preset for t in rec["thumbnails"]):
                    raise DuplicateThumbnailError(
                        f"a '{preset}' thumbnail already exists for image {image_id}"
                    )

                rec["thumbnails"].append(thumbnail_record)
                db[image_id] = rec
                self._write_db_locked(db)
