"""V1 health check routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.services.deploy_info import deployed_commit, scheduler_state

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str
    environment: str
    git_commit: str
    scheduler_enabled: bool
    scheduled_jobs: int


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Versioned health check endpoint."""
    scheduler_enabled, scheduled_jobs = scheduler_state()
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version="0.1.0",
        environment=settings.APP_ENV,
        git_commit=deployed_commit(),
        scheduler_enabled=scheduler_enabled,
        scheduled_jobs=scheduled_jobs,
    )
