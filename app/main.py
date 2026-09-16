from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.rate_limit import RateLimiter
from app.api.controllers import register_routes
from app.database.mongodb import mongodb

setup_logging()
logger = logging.getLogger(__name__)

rate_limiter = RateLimiter(settings.RATE_LIMIT_MAX_REQUESTS, settings.RATE_LIMIT_WINDOW_SECONDS)

# Endpoints orchestrators poll frequently and that shouldn't be rate limited
# or spam the access log.
_UNTHROTTLED_PATHS = {"/healthz", "/readyz"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongodb.connect()
    mongodb.create_indexes()
    yield
    mongodb.close()


app = FastAPI(title="image-thumbnail-service", lifespan=lifespan)


@app.middleware("http")
async def rate_limit_and_access_log(request: Request, call_next):
    if request.url.path in _UNTHROTTLED_PATHS:
        return await call_next(request)

    client_key = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_key):
        logger.warning("Rate limit exceeded for %s on %s %s", client_key, request.method, request.url.path)
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=status.HTTP_429_TOO_MANY_REQUESTS)

    start = time.monotonic()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        status_code = response.status_code if response is not None else 500
        if status_code >= 500:
            log = logger.error
        elif status_code >= 400:
            log = logger.warning
        else:
            log = logger.info
        log("%s %s -> %s (%.1fms)", request.method, request.url.path, status_code, duration_ms)


@app.get("/healthz")
def healthz():
    """Liveness: is the process up and able to respond at all."""
    return JSONResponse({"status": "ok"})


@app.get("/readyz")
def readyz():
    """Readiness: is the app able to serve real requests (i.e. is MongoDB reachable)."""
    if mongodb.ping():
        return JSONResponse({"status": "ready", "database": "ok"})
    return JSONResponse(
        {"status": "not_ready", "database": "unavailable"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


register_routes(app)
