"""V1 API routes."""

from fastapi import APIRouter, Depends

from app.api.routes.v1 import auth, economics, health, ic3, ingest, nvd, vulnerabilities
from app.api.routes.v1.auth import get_current_user

router = APIRouter()

# Public routes — no auth required
router.include_router(health.router, tags=["health"])
router.include_router(auth.router)

# Protected routes — require valid Firebase token
_auth = [Depends(get_current_user)]

router.include_router(
    vulnerabilities.router,
    prefix="/vulnerabilities",
    tags=["vulnerabilities"],
    dependencies=_auth,
)
router.include_router(ic3.router, prefix="/ic3", tags=["ic3"], dependencies=_auth)
router.include_router(nvd.router, prefix="/nvd", tags=["nvd"], dependencies=_auth)
router.include_router(economics.router, prefix="/economics", tags=["economics"], dependencies=_auth)
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"], dependencies=_auth)
