import pytest

from app.services.upload_validation import UploadValidationError, validate_filename, validate_upload

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


@pytest.mark.parametrize(
    "filename",
    [None, "", "   ", "..", "../etc/passwd", "a/b.jpg", "a\\b.jpg"],
)
def test_validate_filename_rejects_bad_names(filename):
    with pytest.raises(UploadValidationError):
        validate_filename(filename)


def test_validate_filename_accepts_plain_name():
    assert validate_filename("photo.jpg") == "photo.jpg"


def test_validate_upload_accepts_matching_jpeg():
    validate_upload("photo.jpg", "image/jpeg", JPEG_BYTES, ("image/jpeg", "image/png"), 1000)


def test_validate_upload_rejects_empty_content():
    with pytest.raises(UploadValidationError, match="empty"):
        validate_upload("photo.jpg", "image/jpeg", b"", ("image/jpeg",), 1000)


def test_validate_upload_rejects_oversized_content():
    with pytest.raises(UploadValidationError, match="maximum"):
        validate_upload("photo.jpg", "image/jpeg", JPEG_BYTES, ("image/jpeg",), max_size_bytes=4)


def test_validate_upload_rejects_disallowed_content_type():
    with pytest.raises(UploadValidationError, match="unsupported content type"):
        validate_upload("photo.gif", "image/gif", JPEG_BYTES, ("image/jpeg", "image/png"), 1000)


def test_validate_upload_rejects_content_type_signature_mismatch():
    with pytest.raises(UploadValidationError, match="does not match declared content type"):
        validate_upload("photo.png", "image/png", JPEG_BYTES, ("image/jpeg", "image/png"), 1000)


def test_validate_upload_rejects_unrecognized_binary():
    with pytest.raises(UploadValidationError, match="not a recognized image format"):
        validate_upload("photo.jpg", "image/jpeg", b"not-an-image" * 5, ("image/jpeg",), 1000)


def test_validate_upload_rejects_missing_filename():
    with pytest.raises(UploadValidationError):
        validate_upload(None, "image/jpeg", JPEG_BYTES, ("image/jpeg",), 1000)
