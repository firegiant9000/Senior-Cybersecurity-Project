"""Data-source transparency endpoint — single source of truth for widget badges."""

from fastapi import APIRouter, Response

from app.services.data_status import DataStatusResponse, list_data_status

router = APIRouter()

# Registry is in-process and changes only on deploy. A 5-minute browser cache
# is more than enough headroom for the frontend's per-session singleton without
# burning request volume on a hot dashboard render.
_CACHE_CONTROL = "public, max-age=300"


@router.get("/data-status", response_model=DataStatusResponse)
async def get_data_status(response: Response) -> DataStatusResponse:
    """Return the source-status registry for every dashboard dataset.

    Used by the frontend to render a `real | static | mocked | pending` badge
    on each widget. Centralized so the dashboard, docs, and audit cannot drift.
    """
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return DataStatusResponse(items=list_data_status())
