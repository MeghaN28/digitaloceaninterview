from pydantic import BaseSettings


class Settings(BaseSettings):
    STORAGE_DIR: str = "data/storage"
    DB_FILE: str = "data/db.json"
    THUMBNAILS_DIR: str = "data/thumbnails"
    ALLOWED_CONTENT_TYPES: tuple = ("image/jpeg", "image/png", "image/webp")

    class Config:
        env_file = ".env"


settings = Settings()
