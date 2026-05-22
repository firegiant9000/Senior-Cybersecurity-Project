"""Tests for the source-status registry contract.

The registry in ``app/services/data_status.py`` is the single source of truth
shared by the dashboard badges, the human ``docs/DATA_SOURCE_STATUS.md``
mirror, and the audit story. These tests guard the contract so silent drift
(duplicate keys, unknown status values, empty registry after a refactor)
fails CI instead of shipping.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.data_status import (
    DatasetStatus,
    list_data_status,
)

_ALLOWED_STATUSES = {"real", "static", "mocked", "pending"}


def test_registry_has_entries():
    items = list_data_status()
    assert len(items) >= 10, "registry shrank unexpectedly — dashboard badges depend on it"


def test_registry_keys_unique():
    items = list_data_status()
    keys = [i.key for i in items]
    assert len(keys) == len(set(keys)), f"duplicate keys in registry: {keys}"


def test_registry_statuses_are_valid():
    for item in list_data_status():
        assert item.status in _ALLOWED_STATUSES, (
            f"{item.key} has invalid status {item.status!r}; "
            f"expected one of {_ALLOWED_STATUSES}"
        )


def test_registry_items_have_required_fields():
    for item in list_data_status():
        assert isinstance(item, DatasetStatus)
        assert item.key, "every registry entry must have a non-empty key"
        assert item.label, f"{item.key} missing human label"
        assert item.source, f"{item.key} missing source description"


@pytest.mark.asyncio
async def test_data_status_endpoint_returns_full_registry(client: AsyncClient):
    resp = await client.get("/api/v1/data-status")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert len(body["items"]) == len(list_data_status())


@pytest.mark.asyncio
async def test_data_status_endpoint_sets_cache_control(client: AsyncClient):
    resp = await client.get("/api/v1/data-status")
    assert resp.status_code == 200
    cache = resp.headers.get("cache-control", "")
    assert "max-age" in cache, f"Cache-Control should set max-age; got {cache!r}"
