class DuplicateThumbnailError(Exception):
    """Raised when a preset thumbnail already exists for an image. -> HTTP 409"""
