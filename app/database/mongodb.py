import logging
from typing import Optional

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.core.metrics import db_metrics, timed

logger = logging.getLogger(__name__)


class MongoDB:
    """Owns the single MongoDB client/connection pool for the app's lifetime."""

    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None

    def connect(self) -> None:
        self.client = MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
            maxPoolSize=settings.MONGO_MAX_POOL_SIZE,
            minPoolSize=settings.MONGO_MIN_POOL_SIZE,
        )
        self.db = self.client[settings.MONGODB_DATABASE]
        # fail fast at startup instead of on the first request
        self.client.admin.command("ping")
        logger.info("Connected to MongoDB database '%s'", settings.MONGODB_DATABASE)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            logger.info("Closed MongoDB connection")
        self.client = None
        self.db = None

    def ping(self) -> bool:
        if self.client is None:
            return False
        try:
            with timed(db_metrics, "mongodb.ping"):
                self.client.admin.command("ping")
            return True
        except PyMongoError:
            logger.exception("MongoDB ping failed")
            return False

    @property
    def images(self) -> Collection:
        return self.db["images"]

    @property
    def thumbnails(self) -> Collection:
        return self.db["thumbnails"]

    def create_indexes(self) -> None:
        self.images.create_index([("image_id", ASCENDING)], unique=True, name="uniq_image_id")
        # Content-hash dedup: two uploads of byte-identical content collide
        # here and the second is treated as a repeat of the first (same
        # image_id returned) instead of creating a duplicate document.
        # Partial so it never applies to any legacy doc without the field.
        self.images.create_index(
            [("content_hash", ASCENDING)],
            unique=True,
            name="uniq_content_hash",
            partialFilterExpression={"content_hash": {"$type": "string"}},
        )

        self.thumbnails.create_index([("image_id", ASCENDING)], name="image_id_idx")
        # Unique per (image_id, preset) only when preset is an actual string.
        # Custom-dimension thumbnails have preset=None, so a plain unique index
        # on (image_id, preset) would let only ONE custom thumbnail exist per
        # image (Mongo treats null as a value for uniqueness purposes). The
        # partialFilterExpression scopes the constraint to preset thumbnails
        # only, leaving custom-size thumbnails unrestricted.
        self.thumbnails.create_index(
            [("image_id", ASCENDING), ("preset", ASCENDING)],
            unique=True,
            name="uniq_image_id_preset",
            partialFilterExpression={"preset": {"$type": "string"}},
        )
        logger.info("Ensured MongoDB indexes")


mongodb = MongoDB()
