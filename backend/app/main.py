"""Application main entry point."""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import func, select

from app.api.routes import health, v1
from app.core.config import settings
from app.core.firebase import init_firebase
from app.core.limiter import limiter
from app.core.logging import setup_logging
from app.db.engine import AsyncSessionLocal, init_db
from app.db.models import CVE, KEV, IC3Incident
from app.integrations.cve_org import aclose_http_client

_log = logging.getLogger(__name__)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 with a JSON body and a seconds-based Retry-After header.

    exc.limit is a slowapi.wrappers.Limit; the underlying limits.RateLimitItem
    lives at exc.limit.limit and exposes GRANULARITY.seconds + multiples.
    """
    try:
        inner = exc.limit.limit
        retry_after = str(inner.GRANULARITY.seconds * (inner.multiples or 1))
    except (AttributeError, TypeError):
        retry_after = "60"
    response = JSONResponse(
        status_code=429,
        content={"error": "Too Many Requests", "detail": str(exc.detail)},
    )
    response.headers["Retry-After"] = retry_after
    return response


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


def _ensure_firebase_credentials() -> None:
    """Write FIREBASE_SERVICE_ACCOUNT_JSON env var to a file if present.

    Render (and similar hosts) don't support mounting secret files directly,
    so the service-account JSON is passed as an env var and written to disk
    at startup so the Firebase Admin SDK can read it via
    GOOGLE_APPLICATION_CREDENTIALS.
    """
    import json
    import tempfile

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        return
    # Validate it's real JSON before writing
    json.loads(sa_json)
    cred_path = os.path.join(tempfile.gettempdir(), "firebase-service-account.json")
    with open(cred_path, "w") as f:
        f.write(sa_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
    _log.info("Wrote Firebase credentials to %s", cred_path)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    _ensure_firebase_credentials()
    try:
        init_firebase()
    except (ValueError, OSError) as exc:  # pragma: no cover - defensive startup guard
        _log.error(
            "Failed to initialize Firebase SDK: %s. "
            "Ensure GOOGLE_APPLICATION_CREDENTIALS is set correctly.",
            exc,
        )
        if settings.APP_ENV not in ("development", "testing"):
            raise SystemExit(
                "FATAL: Firebase initialization failed. "
                "See logs and verify your Google Cloud credentials."
            ) from exc
        _log.warning(
            "Continuing without Firebase because APP_ENV=%r. "
            "Auth-dependent features will not work.",
            settings.APP_ENV,
        )
    await init_db()
    await _auto_ingest()
    yield
    await aclose_http_client()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    if settings.SECRET_KEY == "change-me-in-production":
        if settings.APP_ENV not in ("development", "testing"):
            raise SystemExit(
                "FATAL: SECRET_KEY is set to the default insecure value "
                f"and APP_ENV={settings.APP_ENV!r}. "
                "Set a strong SECRET_KEY (e.g., `openssl rand -hex 32`) "
                "in your environment (for example via a .env file or deployment secrets) before running in production."
            )
        _log.warning(
            "SECRET_KEY is set to the default insecure value. "
            "Set a strong SECRET_KEY in your environment before deploying to production."
        )

    fastapi_app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Cyber Threat Intelligence & Anomaly Detection Platform",
        lifespan=lifespan,
    )

    # Setup logging
    setup_logging(settings.LOG_LEVEL)

    # Register rate limiter
    fastapi_app.state.limiter = limiter
    fastapi_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    fastapi_app.add_middleware(SlowAPIMiddleware)

    # Add CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Retry-After"],
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
