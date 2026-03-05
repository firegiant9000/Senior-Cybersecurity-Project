"""V1 API routes."""

from fastapi import APIRouter

from app.api.routes.v1 import auth, economics, health, ic3, nvd, vulnerabilities

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(auth.router)
router.include_router(
    vulnerabilities.router,
    prefix="/vulnerabilities",
    tags=["vulnerabilities"],
)

router.include_router(ic3.router, prefix="/ic3", tags=["ic3"])
router.include_router(nvd.router, prefix="/nvd", tags=["nvd"])
router.include_router(economics.router, prefix="/economics", tags=["economics"])
