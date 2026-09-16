from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging

from app.core.logging_config import setup_logging
from app.api.controllers import register_routes

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="image-thumbnail-service")


@app.get("/healthz")
def healthz():
    return JSONResponse({"status": "ok"})


register_routes(app)
