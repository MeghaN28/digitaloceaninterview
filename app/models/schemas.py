from typing import List, Optional, Literal
from pydantic import BaseModel, Field, root_validator


class UploadImageResponseItem(BaseModel):
    image_id: str


class UploadImagesResponse(BaseModel):
    images: List[UploadImageResponseItem]


class CreateThumbnailRequest(BaseModel):
    preset: Optional[Literal["small", "medium", "large"]]
    max_width: Optional[int] = Field(None, gt=0)
    max_height: Optional[int] = Field(None, gt=0)

    @root_validator
    def validate_one_of(cls, values):
        preset, w, h = values.get("preset"), values.get("max_width"), values.get("max_height")
        if not preset and (w is None or h is None):
            raise ValueError("Either 'preset' or both 'max_width' and 'max_height' are required")
        return values


class ThumbnailMetadata(BaseModel):
    thumbnail_id: str
    preset: Optional[str]
    width: int
    height: int
    size_bytes: int


class ImageMetadata(BaseModel):
    image_id: str
    original_filename: str
    content_type: str
    width: int
    height: int
    size_bytes: int
    created_at: str
    thumbnails: List[ThumbnailMetadata] = []


class CreateThumbnailResponse(BaseModel):
    image_id: str
    thumbnail_id: str
    width: int
    height: int
    format: str
    size_bytes: int
