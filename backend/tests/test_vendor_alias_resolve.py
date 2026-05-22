"""Phase D7 — VendorAlias repository resolve() unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.vendor_aliases import SqlVendorAliasRepository


def _session_with_scalar(value: str | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_resolve_returns_canonical_when_known() -> None:
    session = _session_with_scalar("microsoft")
    repo = SqlVendorAliasRepository(session)
    assert await repo.resolve("Microsoft Corp") == "microsoft"


@pytest.mark.asyncio
async def test_resolve_falls_back_to_normalized_input() -> None:
    session = _session_with_scalar(None)
    repo = SqlVendorAliasRepository(session)
    assert await repo.resolve("  UnknownVendor Inc.  ") == "unknownvendor inc."


@pytest.mark.asyncio
async def test_resolve_is_case_insensitive_on_input() -> None:
    session = _session_with_scalar("apache")
    repo = SqlVendorAliasRepository(session)
    assert await repo.resolve("APACHE SOFTWARE FOUNDATION") == "apache"
