"""V1 API routes."""

from fastapi import APIRouter, Depends

from app.api.routes.v1 import (
    auth,
    domains,
    economics,
    health,
    ic3,
    ingest,
    nvd,
    onboarding,
    organizations,
    uploads,
    vendors,
    vulnerabilities,
)
from app.core.dependencies import require_role

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
router.include_router(
    economics.router, prefix="/economics", tags=["economics"], dependencies=_viewer
)

router.include_router(
    organizations.router,
    prefix="/organizations",
    tags=["organizations"],
    dependencies=_viewer,
)

# Onboarding: self-service org creation (auth required, no role gate).
router.include_router(onboarding.router)

# Vendors: org tech stack + KEV autocomplete (per-route auth).
router.include_router(vendors.router, tags=["vendors"])

# Uploads: org file upload management (per-route auth).
router.include_router(uploads.router, tags=["uploads"])

# Domains: org domain management (per-route auth).
router.include_router(domains.router, tags=["domains"])

# Ingest router: per-route auth (viewer for reads, admin for trigger).
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
