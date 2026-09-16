import os
from typing import Iterable, Optional

# Magic-byte signatures for the formats we accept. Checking these (instead of
# trusting the client-supplied Content-Type header alone) prevents a
# mislabeled or malicious file from being accepted just because the request
# claimed to be "image/jpeg".
_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


class UploadValidationError(ValueError):
    """Malformed request: bad/missing filename, empty content. -> HTTP 400"""


class UploadTooLargeError(UploadValidationError):
    """File exceeds the configured size limit. -> HTTP 413"""


class UnsupportedMediaTypeError(UploadValidationError):
    """Content type not allowed, or doesn't match the file's actual bytes. -> HTTP 415"""


def _detect_content_type(content: bytes) -> Optional[str]:
    for content_type, signatures in _SIGNATURES.items():
        if any(content.startswith(sig) for sig in signatures):
            return content_type
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_filename(filename: Optional[str]) -> str:
    if filename is None:
        raise UploadValidationError("filename is required")
    name = filename.strip()
    if not name:
        raise UploadValidationError("filename is required")
    if name in (".", "..") or "/" in name or "\\" in name or os.path.basename(name) != name:
        raise UploadValidationError(f"invalid filename '{filename}'")
    return name


def validate_upload(
    filename: Optional[str],
    content_type: Optional[str],
    content: bytes,
    allowed_content_types: Iterable[str],
    max_size_bytes: int,
) -> None:
    validate_filename(filename)

    if not content:
        raise UploadValidationError("uploaded file is empty")

    if len(content) > max_size_bytes:
        raise UploadTooLargeError(
            f"file exceeds maximum allowed size of {max_size_bytes} bytes"
        )

    if not content_type or content_type not in allowed_content_types:
        raise UnsupportedMediaTypeError(f"unsupported content type '{content_type}'")

    detected_content_type = _detect_content_type(content)
    if detected_content_type is None:
        raise UnsupportedMediaTypeError("file content is not a recognized image format")
    if detected_content_type != content_type:
        raise UnsupportedMediaTypeError(
            f"file content does not match declared content type '{content_type}'"
        )
