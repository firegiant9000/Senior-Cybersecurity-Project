"""Application main entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, v1
from app.core.config import settings
from app.core.logging import setup_logging

_log = logging.getLogger(__name__)


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
