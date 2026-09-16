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

### What's actually stored where

`MongoImageRepository` ([app/repositories/mongo_image_repository.py](app/repositories/mongo_image_repository.py))
backs the live API - `POST /v1/images` writes to `images`, thumbnail
creation writes to `thumbnails`, and `GET /v1/images/{id}` composes the
nested `thumbnails` list by querying the `thumbnails` collection for that
`image_id`. **Image/thumbnail bytes themselves are still local disk files**
(`STORAGE_DIR`/`THUMBNAILS_DIR`) - only metadata moved to Mongo; moving the
actual files to object storage (DigitalOcean Spaces) is separate, later work
and is what the `storage_key` field is reserved for.

Duplicate-preset detection (409) uses the same pre-check + insert pattern
as before, but the *authoritative* guard is now the real unique partial
index in Mongo (`insert_one` raising `DuplicateKeyError`) rather than an
in-process lock - Mongo enforces the constraint atomically across however
many app instances are running, which a local file lock never could.

`LocalImageRepository` ([app/repositories/local_repository.py](app/repositories/local_repository.py))
is no longer used by the live request path - kept around because its test
(`tests/test_local_repository_concurrency.py`) is a concrete demonstration
of the file-corruption bug found and fixed earlier in this project.

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

## Concurrency

**Note:** the load-test numbers below were measured against the app when it
was still backed by `LocalImageRepository` (before the Mongo migration in
"What's actually stored where" above). The lock-based correctness guarantee
they describe now lives in that module for reference only; the live app's
correctness guarantee is Mongo's unique partial index instead. The capacity
ceiling itself (small instance + synchronous Pillow work) is unrelated to
which repository backs metadata and should still apply - re-run the same
load test against the current Mongo-backed path if that needs re-confirming.

`LocalImageRepository` uses a single process-wide lock guarding the entire
read-modify-write cycle of every operation, so concurrent requests can't
corrupt `data/db.json` or silently drop each other's writes (see
[app/repositories/local_repository.py](app/repositories/local_repository.py)).
This was verified with a unit test that reproduces the corruption against the
pre-fix code, and with a live load test against the deployed app:

- **20 concurrent** upload + thumbnail + read cycles: 0 failures, consistent
  data, ~4s total.
- **50 concurrent** (30 worker threads): the app fell over under load
  (request timeouts, DO edge `504`s) but recovered immediately afterward with
  no data corruption and no restart. This is a throughput/capacity ceiling on
  the current small App Platform instance, not a correctness bug - the global
  lock serializes *all* repository operations (not just conflicting ones),
  and thumbnail generation does real CPU work (Pillow decode/resize/encode)
  synchronously. If this needs to scale past ~20-30 concurrent requests,
  the next steps would be: a bigger/multi-instance App Platform plan, a
  per-image lock instead of one global lock, and/or moving thumbnail
  generation off the request thread.

## Error responses

| Status | When | Source |
| --- | --- | --- |
| 400 | Missing/invalid filename, empty file body, no files in the request | upload validation |
| 404 | Unknown `image_id` / `thumbnail_id` | not found |
| 409 | A preset thumbnail (`small`/`medium`/`large`) already exists for that image | duplicate-thumbnail check |
| 413 | Uploaded file exceeds `MAX_UPLOAD_SIZE_BYTES` (default 10 MB) | upload validation |
| 415 | Content-Type not in the allow-list, or the file's actual bytes don't match its declared Content-Type | upload validation (magic-byte check) |
| 429 | Client exceeded `RATE_LIMIT_MAX_REQUESTS` per `RATE_LIMIT_WINDOW_SECONDS` | rate limiter |
| 503 | MongoDB unreachable | `/readyz` |

Duplicate detection only applies to preset thumbnails — custom-dimension
thumbnails (`max_width`/`max_height`) aren't deduped, matching the partial
unique index described above. The check is done atomically inside the
repository's locked read-modify-write (not as a separate pre-check + write),
so two concurrent requests for the same `(image_id, preset)` can't both
succeed.

Rate limiting is a simple in-memory, per-process, per-client-IP fixed window
(`app/core/rate_limit.py`) — there's no shared store (no Redis), so each app
instance enforces its own limit independently. `/healthz` and `/readyz` are
exempt so orchestrator health checks are never throttled.

## Logging & metrics

`app/main.py` has an HTTP middleware that logs every request as
`METHOD PATH -> STATUS (duration_ms)`, at `INFO` for 2xx/3xx, `WARNING` for
4xx, and `ERROR` for 5xx. This covers all the error responses above without
needing a handler-by-handler log call. Uvicorn's own access log runs
alongside it.

The same middleware records latency into an in-memory metrics registry
(`app/core/metrics.py`), segregated two ways:

- **`http`**: keyed by `METHOD route-template` (e.g. `POST /v1/images`,
  `GET /v1/images/{image_id}`) — a route template, not the raw URL, so
  metrics group by endpoint instead of fragmenting into one bucket per
  `image_id`.
- **`db`**: keyed by storage operation (`local_repo.save_image`,
  `local_repo.get_image`, `local_repo.add_thumbnail`,
  `mongo_repo.create_image`, `mongo_repo.find_image`, `mongodb.ping`) - this
  is how the concurrency ceiling above was diagnosed: if `db` latency is low
  but `http` latency for the same request is high, the time is going into
  Pillow image processing, not storage/locking.

Each bucket reports `count`, `errors`, `p50_ms`, `p95_ms`, `p99_ms`, `max_ms`.
Check it with:

```bash
curl localhost:8000/metrics | python -m json.tool
```

This is plain JSON, not Prometheus exposition format, and it's per-process
(resets on restart, not shared across instances) - enough to answer "where is
the latency going" right now; swap for `prometheus-client`/OpenTelemetry if
this needs to feed a real dashboard or survive restarts.

## Streamlit UI

A minimal UI (`streamlit_app.py`) for uploading an image and creating
thumbnails without curl/Postman - point it at either your local server or the
deployed app.

```bash
pip install -r requirements-streamlit.txt
streamlit run streamlit_app.py
```

Then enter the API base URL at the top of the page (e.g.
`http://localhost:8000` or your DigitalOcean App Platform URL) and use the
upload / thumbnail / metadata sections.

## Docker

```bash
docker build -t image-thumbnail-service .
docker run --env-file .env -p 8000:8000 image-thumbnail-service
```

`MONGODB_URI` and `MONGODB_DATABASE` are supplied at runtime via `--env-file`
(or `-e`) — they are never baked into the image or the Dockerfile.

# digitaloceaninterview