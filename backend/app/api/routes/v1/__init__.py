"""V1 API routes."""

from fastapi import APIRouter, Depends, Depends

from app.api.routes.v1 import auth, economics, health, ic3, ingest, nvd, vulnerabilities
from app.core.dependencies import require_role
from app.api.routes.v1.auth import get_current_user

router = APIRouter()

# Health and auth routes remain public.
router.include_router(health.router, tags=["health"])
router.include_router(auth.router)

# All data-read routers require at least the "viewer" role.
_viewer = [Depends(require_role("viewer"))]

router.include_router(
    vulnerabilities.router,
    prefix="/vulnerabilities",
    tags=["vulnerabilities"],
    dependencies=_viewer,
)
router.include_router(ic3.router, prefix="/ic3", tags=["ic3"], dependencies=_viewer)
router.include_router(nvd.router, prefix="/nvd", tags=["nvd"], dependencies=_viewer)
router.include_router(economics.router, prefix="/economics", tags=["economics"], dependencies=_viewer)

# Ingest router: per-route auth (viewer for reads, admin for trigger).
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
