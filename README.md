# image-thumbnail-service

Simple FastAPI service skeleton for uploading images and generating thumbnails.

Run locally:
```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API:
- POST /v1/images -> upload images
- POST /v1/images/{image_id}/thumbnails -> generate thumbnail
- GET /v1/images/{image_id} -> metadata
- GET /v1/images/{image_id}/thumbnails/{thumbnail_id} -> get thumbnail file
- GET /healthz -> health
# digitaloceaninterview