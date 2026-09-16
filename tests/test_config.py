from app.core.config import Settings


def test_mongodb_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://testhost:27017")
    monkeypatch.setenv("MONGODB_DATABASE", "test_db")

    s = Settings()

    assert s.MONGODB_URI == "mongodb://testhost:27017"
    assert s.MONGODB_DATABASE == "test_db"


def test_mongodb_settings_have_sane_defaults(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)

    s = Settings(_env_file=None)

    assert s.MONGODB_URI == "mongodb://localhost:27017"
    assert s.MONGODB_DATABASE == "image_thumbnail_db"
