from pydantic import BaseSettings


class Settings(BaseSettings):
    STORAGE_DIR: str = "data/storage"
    DB_FILE: str = "data/db.json"
    THUMBNAILS_DIR: str = "data/thumbnails"
    ALLOWED_CONTENT_TYPES: tuple = ("image/jpeg", "image/png", "image/webp")
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "image_thumbnail_db"
    MONGO_SERVER_SELECTION_TIMEOUT_MS: int = 5000
    MONGO_MAX_POOL_SIZE: int = 50
    MONGO_MIN_POOL_SIZE: int = 0

    class Config:
        env_file = ".env"


settings = Settings()
