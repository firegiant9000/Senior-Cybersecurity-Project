"""V1 health check routes."""

from fastapi import APIRouter

from app.api.routes.health import HealthResponse, health_check

router = APIRouter()

# Same handler as the root /health, so both paths check the database.
router.get("/health", response_model=HealthResponse)(health_check)
