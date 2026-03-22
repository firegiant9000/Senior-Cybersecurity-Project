"""Application main entry point."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.api.routes import health, v1
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.engine import AsyncSessionLocal, init_db
from app.db.models import CVE, KEV, IC3Incident
from app.integrations.cve_org import aclose_http_client

_log = logging.getLogger(__name__)


async def _run_sequential_ingest(sources: list[str]) -> None:
    """Run ingestion for each source one at a time to avoid DB conflicts."""
    from app.api.routes.v1.ingest import _run_ingestion

    for src in sources:
        _log.info("Starting %s ingestion...", src)
        await _run_ingestion(src)


async def _auto_ingest() -> None:
    """Seed data sources on startup.

    - Default: only ingest sources with no rows in the database.
    - FORCE_SEED=true: re-ingest all sources regardless of existing data.

    Runs sequentially (NVD → CISA KEV → IC3) in a background task
    to avoid duplicate key conflicts between NVD and CISA KEV.
    """
    all_sources = ["nvd", "cisa_kev", "ic3"]

    if settings.FORCE_SEED:
        _log.info("FORCE_SEED=true — re-ingesting all sources: %s", all_sources)
        asyncio.create_task(_run_sequential_ingest(all_sources))
        return

    async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
        nvd_count = (await db.execute(select(func.count()).select_from(CVE))).scalar() or 0
        kev_count = (await db.execute(select(func.count()).select_from(KEV))).scalar() or 0
        ic3_count = (await db.execute(select(func.count()).select_from(IC3Incident))).scalar() or 0

    sources_to_ingest: list[str] = []
    if nvd_count == 0:
        sources_to_ingest.append("nvd")
    if kev_count == 0:
        sources_to_ingest.append("cisa_kev")
    if ic3_count == 0:
        sources_to_ingest.append("ic3")

    if not sources_to_ingest:
        _log.info("All data sources already populated — skipping auto-ingest")
        return

    _log.info("Auto-ingesting empty sources on startup: %s", sources_to_ingest)
    asyncio.create_task(_run_sequential_ingest(sources_to_ingest))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    await _auto_ingest()
    yield
    await aclose_http_client()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    if settings.SECRET_KEY == "change-me-in-production":
        _log.warning(
            "SECRET_KEY is set to the default insecure value. "
            "Set a strong SECRET_KEY in your .env before deploying to production."
        )

    fastapi_app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Cyber Threat Intelligence & Anomaly Detection Platform",
        lifespan=lifespan,
    )

    # Setup logging
    setup_logging(settings.LOG_LEVEL)

    # Add CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    fastapi_app.include_router(health.router)
    fastapi_app.include_router(v1.router, prefix=settings.API_PREFIX)

    @fastapi_app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint with quick API links."""
        return {
            "service": settings.APP_NAME,
            "health": "/health",
            "api_base": settings.API_PREFIX,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return fastapi_app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True,
    )
