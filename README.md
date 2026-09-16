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
- GET /healthz -> liveness
- GET /readyz -> readiness (checks MongoDB)

## Configuration

Copy `.env.example` to `.env` and fill in real values. `.env` is gitignored and
must never be committed.

```
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster-host>/admin?tls=true&authSource=admin
MONGODB_DATABASE=image_thumbnail_db
```

## MongoDB

### Connection flow

`app/database/mongodb.py` owns a single `MongoDB` instance (`mongodb`) that
wraps one `pymongo.MongoClient` — pymongo itself manages a connection pool,
so this one client is reused for the lifetime of the process instead of
opening a new connection per request.

The FastAPI `lifespan` handler in `app/main.py` drives its lifecycle:

```
startup -> mongodb.connect() (creates client, selects DB, pings)
        -> mongodb.create_indexes()
        -> app ready to serve requests
shutdown -> mongodb.close()
```

### Collections & indexes

- `images`: one document per uploaded image. Unique index on `image_id`.
- `thumbnails`: one document per generated thumbnail.
  - Index on `image_id` (list all thumbnails for an image).
  - Unique compound index on `(image_id, preset)`, but scoped with a
    `partialFilterExpression: {"preset": {"$type": "string"}}`. A plain
    unique index on `(image_id, preset)` would break custom-size thumbnails:
    MongoDB treats `null` as a real value for uniqueness, so every
    custom-dimension thumbnail (`preset=None`) for the same image would
    collide on the very first one. The partial index enforces "only one
    `small`/`medium`/`large` thumbnail per image" while leaving
    custom-dimension thumbnails unrestricted. If custom thumbnails later need
    their own dedup rule (e.g. one thumbnail per exact `(image_id, max_width,
    max_height)`), add a separate partial unique index for that case rather
    than overloading this one.

### /healthz vs /readyz

- `/healthz` — liveness. Answers "is the process up and responding at all?"
  Never touches MongoDB, so it can't be dragged down by a DB outage. Used by
  orchestrators to decide whether to restart the container.
- `/readyz` — readiness. Answers "can this instance actually serve traffic?"
  Pings MongoDB and returns `503` if it's unreachable. Used by orchestrators
  / load balancers to decide whether to route traffic to this instance.

## Running locally

```bash
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
curl localhost:8000/healthz
curl localhost:8000/readyz
```

## Verifying the DigitalOcean MongoDB connection

```bash
# quick ping + index check against whatever MONGODB_URI/.env points at
python -c "
from app.database.mongodb import MongoDB
db = MongoDB()
db.connect()
db.create_indexes()
print('ping ok:', db.ping())
print('images indexes:', list(db.images.list_indexes()))
print('thumbnails indexes:', list(db.thumbnails.list_indexes()))
db.close()
"
```

## Tests

- **Unit tests** (`tests/`): config loading, the Mongo repository, and
  `/healthz`/`/readyz`. They use `mongomock` (an in-memory MongoDB fake), so
  they never require network access or real credentials. Run with:
  ```bash
  pytest
  ```
- **Integration tests** (`tests/integration/`): hit a real MongoDB. They're
  marked `integration` and skip themselves unless `MONGODB_URI` is present in
  the environment, so a plain `pytest` run never touches the real database.
  Run explicitly, with credentials supplied via env vars (never hardcoded):
  ```bash
  MONGODB_URI="..." MONGODB_DATABASE="image_thumbnail_db" pytest -m integration
  ```

## Docker

```bash
docker build -t image-thumbnail-service .
docker run --env-file .env -p 8000:8000 image-thumbnail-service
```

`MONGODB_URI` and `MONGODB_DATABASE` are supplied at runtime via `--env-file`
(or `-e`) — they are never baked into the image or the Dockerfile.

# digitaloceaninterview