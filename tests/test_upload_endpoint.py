import io

from PIL import Image


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_valid_jpeg_succeeds(client):
    resp = client.post(
        "/v1/images",
        files={"files": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["images"]) == 1
    assert body["images"][0]["image_id"]


def test_upload_no_files_rejected(client):
    resp = client.post("/v1/images", files={})

    assert resp.status_code in (400, 422)


def test_upload_empty_file_rejected(client):
    resp = client.post(
        "/v1/images",
        files={"files": ("empty.jpg", b"", "image/jpeg")},
    )

    assert resp.status_code == 400


def test_upload_oversized_file_rejected(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 5)

    resp = client.post(
        "/v1/images",
        files={"files": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
    )

    assert resp.status_code == 413
    assert "maximum" in resp.json()["detail"]


def test_upload_disallowed_content_type_rejected(client):
    resp = client.post(
        "/v1/images",
        files={"files": ("photo.gif", b"GIF89a" + b"\x00" * 20, "image/gif")},
    )

    assert resp.status_code == 415


def test_upload_signature_mismatch_rejected(client):
    resp = client.post(
        "/v1/images",
        files={"files": ("photo.png", _jpeg_bytes(), "image/png")},
    )

    assert resp.status_code == 415
    assert "does not match declared content type" in resp.json()["detail"]


def test_upload_missing_filename_rejected(client):
    resp = client.post(
        "/v1/images",
        files={"files": ("", _jpeg_bytes(), "image/jpeg")},
    )

    assert resp.status_code in (400, 422)
