"""API routes."""

from fastapi import APIRouter

from app.api.routes import health, v1

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(v1.router, tags=["v1"])
