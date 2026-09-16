from typing import Protocol, Optional


class ImageRecord(dict):
    pass


class ImageRepository(Protocol):
    def save_image(self, image_id: str, filename: str, content_type: str, width: int, height: int, size_bytes: int, created_at: str) -> None:
        ...

    def get_image(self, image_id: str) -> Optional[ImageRecord]:
        ...

    def add_thumbnail(self, image_id: str, thumbnail_record: dict) -> None:
        ...
