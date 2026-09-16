import threading

from app.repositories.local_repository import LocalImageRepository

N = 20


def test_concurrent_add_thumbnail_does_not_lose_updates(tmp_path):
    db_file = str(tmp_path / "db.json")

    # controllers.py builds a fresh LocalImageRepository per request via
    # get_repo(), so simulate that here instead of sharing one instance.
    for i in range(N):
        LocalImageRepository(db_file).save_image(
            f"img{i}", f"file{i}.jpg", "image/jpeg", 10, 10, 100, "2026-01-01T00:00:00Z"
        )

    def add_thumb(i):
        LocalImageRepository(db_file).add_thumbnail(
            f"img{i}",
            {
                "thumbnail_id": f"t{i}",
                "preset": "small",
                "width": 5,
                "height": 5,
                "size_bytes": 10,
                "filename": f"t{i}.jpg",
                "created_at": "2026-01-01T00:00:00Z",
            },
        )

    threads = [threading.Thread(target=add_thumb, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final_repo = LocalImageRepository(db_file)
    lost = [i for i in range(N) if len(final_repo.get_image(f"img{i}")["thumbnails"]) != 1]
    assert not lost, f"lost thumbnail updates for images: {lost}"
