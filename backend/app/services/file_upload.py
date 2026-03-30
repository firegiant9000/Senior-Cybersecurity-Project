"""File upload service — handles storage, sanitization, and deletion."""

import os
import re
import uuid

from fastapi import HTTPException, UploadFile

from app.core.config import settings


def sanitize_filename(name: str) -> str:
    """Strip dangerous characters and truncate to a safe length."""
    # Remove path separators and null bytes
    name = name.replace("/", "").replace("\\", "").replace("\0", "")
    # Remove parent-directory traversal
    name = name.replace("..", "")
    # Collapse whitespace
    name = re.sub(r"\s+", "_", name.strip())
    # Remove any remaining non-printable characters
    name = re.sub(r"[^\w.\-]", "", name)
    # Ensure non-empty
    if not name:
        name = "unnamed"
    # Truncate to 200 chars
    return name[:200]


def generate_stored_name(original: str) -> str:
    """Return a collision-safe filename: {uuid}_{sanitized}."""
    return f"{uuid.uuid4().hex}_{sanitize_filename(original)}"


async def save_upload(
    org_id: int,
    file: UploadFile,
) -> tuple[str, str, int]:
    """Validate and persist an uploaded file.

    Returns (original_filename, stored_filename, file_size_bytes).
    Raises HTTPException on validation failure.
    """
    # Validate content type (reject missing or disallowed types)
    if not file.content_type or file.content_type not in settings.ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type or 'unknown'}' not allowed. "
            f"Accepted: {', '.join(settings.ALLOWED_UPLOAD_TYPES)}",
        )

    # Read and check size
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {max_mb:.0f} MB",
        )

    original = file.filename or "unnamed"
    stored = generate_stored_name(original)

    # Ensure org-scoped directory exists
    org_dir = os.path.join(settings.UPLOAD_DIR, str(org_id))
    try:
        os.makedirs(org_dir, exist_ok=True)
    except PermissionError:
        raise HTTPException(
            status_code=500,
            detail="Server file storage is not writable. Contact an administrator.",
        )

    # Write file
    path = os.path.join(org_dir, stored)
    try:
        with open(path, "wb") as f:
            f.write(content)
    except PermissionError:
        raise HTTPException(
            status_code=500,
            detail="Server file storage is not writable. Contact an administrator.",
        )

    return original, stored, len(content)


def delete_upload_file(org_id: int, stored_filename: str) -> None:
    """Remove a file from disk. No-op if already missing."""
    path = os.path.join(settings.UPLOAD_DIR, str(org_id), stored_filename)
    if os.path.exists(path):
        os.remove(path)


def get_upload_path(org_id: int, stored_filename: str) -> str:
    """Return the absolute path to a stored upload."""
    return os.path.join(settings.UPLOAD_DIR, str(org_id), stored_filename)
