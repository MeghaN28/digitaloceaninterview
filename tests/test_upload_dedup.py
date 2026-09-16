import io

from PIL import Image


def _jpeg_bytes(color="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 100), color=color).save(buf, format="JPEG")
    return buf.getvalue()


def test_reuploading_identical_content_returns_same_image_id(client):
    content = _jpeg_bytes()

    first = client.post("/v1/images", files={"files": ("a.jpg", content, "image/jpeg")})
    second = client.post("/v1/images", files={"files": ("b.jpg", content, "image/jpeg")})

    assert first.status_code == 200
    assert second.status_code == 200
    first_id = first.json()["images"][0]["image_id"]
    second_id = second.json()["images"][0]["image_id"]
    assert first_id == second_id


def test_different_content_gets_different_image_ids(client):
    red = client.post("/v1/images", files={"files": ("a.jpg", _jpeg_bytes("red"), "image/jpeg")})
    blue = client.post("/v1/images", files={"files": ("b.jpg", _jpeg_bytes("blue"), "image/jpeg")})

    red_id = red.json()["images"][0]["image_id"]
    blue_id = blue.json()["images"][0]["image_id"]
    assert red_id != blue_id


def test_dedup_within_the_same_batch_request(client):
    content = _jpeg_bytes()

    resp = client.post(
        "/v1/images",
        files=[
            ("files", ("a.jpg", content, "image/jpeg")),
            ("files", ("b.jpg", content, "image/jpeg")),
        ],
    )

    assert resp.status_code == 200
    ids = [img["image_id"] for img in resp.json()["images"]]
    assert len(ids) == 2
    assert ids[0] == ids[1]
