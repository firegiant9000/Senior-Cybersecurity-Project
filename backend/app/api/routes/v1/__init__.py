"""V1 API routes."""

from fastapi import APIRouter

from app.api.routes.v1 import health, vulnerabilities

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(
    vulnerabilities.router,
    prefix="/vulnerabilities",
    tags=["vulnerabilities"],
)
