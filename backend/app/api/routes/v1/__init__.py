"""V1 API routes."""

from fastapi import APIRouter, Depends

from app.api.routes.v1 import (
    analytics,
    anomalies,
    assessments,
    auth,
    data_lifecycle,
    data_status,
    domains,
    economics,
    health,
    ic3,
    ingest,
    integrations,
    inventory,
    members,
    nvd,
    onboarding,
    organizations,
    public,
    uploads,
    vendors,
    vulnerabilities,
)
from app.core.dependencies import require_role

router = APIRouter()

# Health and auth routes remain public.
router.include_router(health.router, tags=["health"])
router.include_router(auth.router)

# Public aggregate stats for logged-out landing page.
router.include_router(public.router, tags=["public"])

# Data-source transparency: public so the landing page can render badges too.
router.include_router(data_status.router, tags=["data-status"])

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

# Org data-lifecycle (delete + export) — admin-only, audit-logged.
router.include_router(data_lifecycle.router, tags=["data-lifecycle"])

# Onboarding: self-service org creation (auth required, no role gate).
router.include_router(onboarding.router)

# Assessments: versioned assessment submission CRUD.
router.include_router(assessments.router)

# Vendors: org tech stack + KEV autocomplete (per-route auth).
router.include_router(vendors.router, tags=["vendors"])

# Uploads: org file upload management (per-route auth).
router.include_router(uploads.router, tags=["uploads"])

# Inventory: CSV asset upload + scan runs + assets list (per-route auth).
router.include_router(inventory.router, tags=["inventory"])

# Integrations: M365 / Entra OAuth spike (Phase E, feature-flagged).
router.include_router(integrations.router)

# Activation analytics: onboarding-funnel events (Phase F4).
router.include_router(analytics.router, tags=["analytics"])

# Domains: org domain management (per-route auth).
router.include_router(domains.router, tags=["domains"])

# Members & Invites: org membership and invite management (per-route auth).
router.include_router(members.router, tags=["members"])

# Ingest router: per-route auth (viewer for reads, admin for trigger).
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])

# Anomaly detection: IC3 and vendor anomalies (viewer role required).
router.include_router(
    anomalies.router,
    prefix="/anomalies",
    tags=["anomalies"],
    dependencies=_viewer,
)
