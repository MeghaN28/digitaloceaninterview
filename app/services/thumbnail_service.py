import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

from PIL import Image

from app.core.config import settings
from app.repositories.local_repository import DuplicateThumbnailError

logger = logging.getLogger(__name__)


PRESETS = {
    "small": (500, 500),
    "medium": (800, 800),
    "large": (1200, 1200),
}


class ThumbnailService:
    def __init__(self, repo, storage_dir: str = None, thumbs_dir: str = None):
        self.repo = repo
        self.storage_dir = Path(storage_dir or settings.STORAGE_DIR)
        self.thumbs_dir = Path(thumbs_dir or settings.THUMBNAILS_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)

    def create_thumbnail(self, image_id: str, max_w: int, max_h: int, preset: Optional[str] = None) -> dict:
        rec = self.repo.get_image(image_id)
        if not rec:
            raise KeyError("image not found")

        # Fast pre-check to skip the resize work for the common case; the
        # authoritative check is the atomic one inside repo.add_thumbnail,
        # since a concurrent request could create the same preset between
        # this check and the write below.
        if preset is not None and any(t.get("preset") == preset for t in rec.get("thumbnails", [])):
            raise DuplicateThumbnailError(f"a '{preset}' thumbnail already exists for image {image_id}")

        orig_path = self.storage_dir / f"{image_id}"
        if not orig_path.exists():
            raise FileNotFoundError("original file missing")

        with Image.open(orig_path) as img:
            img_format = img.format or "JPEG"
            orig_w, orig_h = img.size
            img_copy = img.copy()
            img_copy.thumbnail((max_w, max_h))
            out_w, out_h = img_copy.size

            thumb_id = uuid4().hex
            ext = img_format.lower() if img_format else "jpg"
            thumb_name = f"{image_id}_{thumb_id}.{ext}"
            thumb_path = self.thumbs_dir / thumb_name

            buf = io.BytesIO()
            img_copy.save(buf, format=img_format)
            size_bytes = buf.tell()
            buf.seek(0)

            with open(thumb_path, "wb") as f:
                f.write(buf.read())

        thumb_record = {
            "thumbnail_id": thumb_id,
            "preset": preset,
            "width": out_w,
            "height": out_h,
            "size_bytes": size_bytes,
            "filename": thumb_name,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        try:
            self.repo.add_thumbnail(image_id, thumb_record)
        except DuplicateThumbnailError:
            thumb_path.unlink(missing_ok=True)
            raise

        logger.info("Created thumbnail %s for image %s", thumb_id, image_id)

        return {
            "image_id": image_id,
            "thumbnail_id": thumb_id,
            "width": out_w,
            "height": out_h,
            "format": img_format.lower(),
            "size_bytes": size_bytes,
        }
