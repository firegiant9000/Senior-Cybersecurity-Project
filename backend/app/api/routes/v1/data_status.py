"""Data-source transparency endpoint — single source of truth for widget badges."""

from fastapi import APIRouter

from app.services.data_status import DataStatusResponse, list_data_status

router = APIRouter()


@router.get("/data-status", response_model=DataStatusResponse)
async def get_data_status() -> DataStatusResponse:
    """Return the source-status registry for every dashboard dataset.

    Used by the frontend to render a `real | static | mocked | pending` badge
    on each widget. Centralized so the dashboard, docs, and audit cannot drift.
    """
    return DataStatusResponse(items=list_data_status())
