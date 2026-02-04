"""V1 health check routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Versioned health check endpoint."""
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version="0.1.0",
        environment=settings.APP_ENV,
    )
