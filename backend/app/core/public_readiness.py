"""Feature flag for the public readiness check (#293).

Off by default. While off, every public readiness route answers 404 as if it
did not exist. Turn it on only after #209 (per-client rate-limit key).
"""

from fastapi import HTTPException, status

from app.core.config import settings


def require_public_readiness() -> None:
    """Route dependency: 404 unless ENABLE_PUBLIC_READINESS is on."""
    if not settings.ENABLE_PUBLIC_READINESS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
