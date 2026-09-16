import logging
from datetime import datetime
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from typing import List
from uuid import uuid4

from app.core.config import settings
from app.models import schemas
from app.repositories.local_repository import LocalImageRepository
from app.services.thumbnail_service import ThumbnailService, PRESETS
from app.services.upload_validation import UploadValidationError, validate_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


def get_repo():
    return LocalImageRepository(settings.DB_FILE)


def get_thumb_service(repo=Depends(get_repo)):
    return ThumbnailService(repo)


@router.post("/images", response_model=schemas.UploadImagesResponse)
async def upload_images(files: List[UploadFile] = File(...), repo: LocalImageRepository = Depends(get_repo)):
    if not files:
        raise HTTPException(status_code=400, detail="at least one file is required")

    images = []
    for upload in files:
        content = await upload.read()

        try:
            validate_upload(
                upload.filename,
                upload.content_type,
                content,
                settings.ALLOWED_CONTENT_TYPES,
                settings.MAX_UPLOAD_SIZE_BYTES,
            )
        except UploadValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        image_id = uuid4().hex
        filename = f"{image_id}"
        storage_dir = settings.STORAGE_DIR
        from pathlib import Path

        Path(storage_dir).mkdir(parents=True, exist_ok=True)
        path = Path(storage_dir) / filename
        with open(path, "wb") as f:
            f.write(content)

        # read image to get dimensions
        from PIL import Image, UnidentifiedImageError
        import io

        try:
            img = Image.open(io.BytesIO(content))
            width, height = img.size
        except UnidentifiedImageError:
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="file could not be read as an image")

        size_bytes = len(content)
        created_at = datetime.utcnow().isoformat() + "Z"

        repo.save_image(image_id, upload.filename, upload.content_type, width, height, size_bytes, created_at)
        images.append({"image_id": image_id})
        logger.info("Saved image %s (%s bytes)", image_id, size_bytes)

    return {"images": images}


@router.post("/images/{image_id}/thumbnails", response_model=schemas.CreateThumbnailResponse)
def create_thumbnail(image_id: str, payload: schemas.CreateThumbnailRequest, service: ThumbnailService = Depends(get_thumb_service)):
    if payload.preset:
        if payload.preset not in PRESETS:
            raise HTTPException(status_code=400, detail="invalid preset")
        max_w, max_h = PRESETS[payload.preset]
        preset = payload.preset
    else:
        max_w, max_h = payload.max_width, payload.max_height
        preset = None

    try:
        out = service.create_thumbnail(image_id, max_w, max_h, preset=preset)
    except KeyError:
        raise HTTPException(status_code=404, detail="image not found")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="original file missing")

    return out


@router.get("/images/{image_id}", response_model=schemas.ImageMetadata)
def get_image_metadata(image_id: str, repo: LocalImageRepository = Depends(get_repo)):
    rec = repo.get_image(image_id)
    if not rec:
        raise HTTPException(status_code=404, detail="image not found")
    return rec


@router.get("/images/{image_id}/thumbnails/{thumbnail_id}")
def get_thumbnail_file(image_id: str, thumbnail_id: str, repo: LocalImageRepository = Depends(get_repo)):
    rec = repo.get_image(image_id)
    if not rec:
        raise HTTPException(status_code=404, detail="image not found")

    thumbs = rec.get("thumbnails", [])
    match = next((t for t in thumbs if t.get("thumbnail_id") == thumbnail_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="thumbnail not found")

    from pathlib import Path

    path = Path(settings.THUMBNAILS_DIR) / match.get("filename")
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing")

    return FileResponse(path, media_type=rec.get("content_type"), filename=match.get("filename"))


def register_routes(app: FastAPI):
    app.include_router(router)
