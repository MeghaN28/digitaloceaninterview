from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.metrics import db_metrics, http_metrics
from app.core.rate_limit import RateLimiter
from app.api.controllers import register_routes
from app.database.mongodb import mongodb

setup_logging()
logger = logging.getLogger(__name__)

rate_limiter = RateLimiter(settings.RATE_LIMIT_MAX_REQUESTS, settings.RATE_LIMIT_WINDOW_SECONDS)

# Endpoints orchestrators/dashboards poll frequently and that shouldn't be
# rate limited (they're still logged and measured, just not throttled).
_UNTHROTTLED_PATHS = {"/healthz", "/readyz", "/metrics"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongodb.connect()
    mongodb.create_indexes()
    yield
    mongodb.close()


app = FastAPI(title="image-thumbnail-service", lifespan=lifespan)


@app.middleware("http")
async def rate_limit_and_access_log(request: Request, call_next):
    throttled = request.url.path not in _UNTHROTTLED_PATHS
    if throttled:
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

        # Use the matched route's path template (e.g. "/v1/images/{image_id}")
        # rather than the raw URL, so metrics group by endpoint instead of
        # fragmenting into one bucket per image_id.
        route = request.scope.get("route")
        route_label = route.path if route is not None else request.url.path
        http_metrics.record(f"{request.method} {route_label}", duration_ms, is_error=status_code >= 500)

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


@app.get("/metrics")
def metrics():
    """Latency/count breakdown, segregated by HTTP route+method and by
    storage-layer operation, each with p50/p95/p99. Not Prometheus format -
    plain JSON is enough to see where latency is going for now; swap for
    prometheus-client/OpenTelemetry if this needs to feed a real dashboard."""
    return JSONResponse({"http": http_metrics.snapshot(), "db": db_metrics.snapshot()})


register_routes(app)
