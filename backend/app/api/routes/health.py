"""Health check routes."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.db.engine import get_health_engine
from app.services.deploy_info import deployed_commit, scheduler_state
from app.services.health import cached_database_reachable

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str
    environment: str
    database: str
    git_commit: str
    scheduler_enabled: bool
    scheduled_jobs: int  # registered ingest_<source> jobs only (not sweeps/matcher/retention)


@router.get("/health", response_model=HealthResponse)
async def health_check(
    response: Response,
    db_engine: AsyncEngine = Depends(get_health_engine),
) -> HealthResponse:
    """Liveness plus a `SELECT 1`. 503 when the database is unreachable.

    Unauthenticated and not rate-limited (Render's health check).
    """
    ok = await cached_database_reachable(db_engine)
    if not ok:
        response.status_code = 503
    state = "ok" if ok else "unavailable"
    scheduler_enabled, scheduled_jobs = scheduler_state()
    return HealthResponse(
        status=state,
        service=settings.APP_NAME,
        version="0.1.0",
        environment=settings.APP_ENV,
        database=state,
        git_commit=deployed_commit(),
        scheduler_enabled=scheduler_enabled,
        scheduled_jobs=scheduled_jobs,
    )
