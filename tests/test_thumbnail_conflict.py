import io

from PIL import Image


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 100), color="blue").save(buf, format="JPEG")
    return buf.getvalue()


def _upload_image(client) -> str:
    resp = client.post("/v1/images", files={"files": ("photo.jpg", _jpeg_bytes(), "image/jpeg")})
    return resp.json()["images"][0]["image_id"]


def test_duplicate_preset_thumbnail_returns_409(client):
    image_id = _upload_image(client)

    first = client.post(f"/v1/images/{image_id}/thumbnails", json={"preset": "small"})
    assert first.status_code == 200

    second = client.post(f"/v1/images/{image_id}/thumbnails", json={"preset": "small"})
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_different_presets_are_not_a_conflict(client):
    image_id = _upload_image(client)

    small = client.post(f"/v1/images/{image_id}/thumbnails", json={"preset": "small"})
    medium = client.post(f"/v1/images/{image_id}/thumbnails", json={"preset": "medium"})

    assert small.status_code == 200
    assert medium.status_code == 200


def test_multiple_custom_dimension_thumbnails_are_not_a_conflict(client):
    image_id = _upload_image(client)

    first = client.post(f"/v1/images/{image_id}/thumbnails", json={"max_width": 50, "max_height": 50})
    second = client.post(f"/v1/images/{image_id}/thumbnails", json={"max_width": 60, "max_height": 60})

    assert first.status_code == 200
    assert second.status_code == 200
