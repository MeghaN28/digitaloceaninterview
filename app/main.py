from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from app.core.logging_config import setup_logging
from app.api.controllers import register_routes
from app.database.mongodb import mongodb

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongodb.connect()
    mongodb.create_indexes()
    yield
    mongodb.close()


app = FastAPI(title="image-thumbnail-service", lifespan=lifespan)


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
