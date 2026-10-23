"""Fixtures for the tenancy suite: a seeded multi-org world, a client factory and no egress.

Everything here runs under stage A's real token verification. Never use the global
`client` fixture or `dependency_overrides[get_current_user]` in this folder.
"""

import importlib
from collections.abc import AsyncGenerator, Awaitable, Callable
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.config import settings
from app.integrations import m365 as graph
from tests.authz._issuer import mint_id_token
from tests.authz.tenancy._world import (
    _TEST_FERNET_KEY,
    World,
    WorldUser,
    build_world,
    drop_world,
)

# (module, attribute) pairs that would reach the network or spawn background work. Patched
# at the module that looks the name up, because `from x import y` binds a private copy.
EGRESS_SITES: list[tuple[str, str]] = [
    ("app.api.routes.v1.domains", "run_tier2_checks"),
    ("app.services.findings_engine", "run_tier1_checks"),
    ("app.services.findings_engine", "run_tier2_checks"),
    ("app.services.ai_summary", "_call_gemini"),
    ("app.integrations.m365", "refresh_access_token"),
    ("app.integrations.m365", "list_managed_devices"),
    ("app.workers.matcher_job", "trigger_matcher_async"),
    ("app.api.routes.v1.domains", "fire_and_forget_normalization_log"),
    ("app.api.routes.v1.vendors", "fire_and_forget_normalization_log"),
    ("app.services.vendor_alerts", "fire_and_forget_normalization_log"),
    # organizations.py imports it inside the function, so the source module is the site.
    ("app.repositories.normalization_log_repo", "fire_and_forget_normalization_log"),
]


def _mark(fn):
    fn._egress_stub = True
    return fn


@_mark
async def _stub_tier1(*_args, **_kwargs):
    dns = SimpleNamespace(error="egress disabled")
    http = SimpleNamespace(reachable=False)
    ssl = SimpleNamespace(reachable=False)
    return dns, http, ssl, None


@_mark
async def _stub_tier2(*_args, **_kwargs):
    return None, None, None, None


@_mark
async def _stub_gemini(*_args, **_kwargs):
    return ""


@_mark
async def _stub_refresh_access_token(*_args, **_kwargs):
    return graph.TokenResponse(
        access_token="egress-disabled",  # noqa: S106
        refresh_token=None,
        expires_in=3600,
        scope="",
        tenant_id=None,
        account_label=None,
    )


@_mark
async def _stub_list_managed_devices(*_args, **_kwargs):
    return []


@_mark
def _stub_noop(*_args, **_kwargs):
    return None


_STUBS = {
    "run_tier1_checks": _stub_tier1,
    "run_tier2_checks": _stub_tier2,
    "_call_gemini": _stub_gemini,
    "refresh_access_token": _stub_refresh_access_token,
    "list_managed_devices": _stub_list_managed_devices,
    "trigger_matcher_async": _stub_noop,
    "fire_and_forget_normalization_log": _stub_noop,
}


@pytest.fixture
def egress_sites() -> list[tuple[str, str]]:
    return EGRESS_SITES


@pytest.fixture(autouse=True)
def _tenancy_settings(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_M365_INTEGRATION", True)
    monkeypatch.setattr(settings, "M365_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "M365_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        settings, "M365_REDIRECT_URI", "http://test/api/v1/integrations/m365/callback"
    )
    monkeypatch.setattr(settings, "M365_FERNET_KEY", _TEST_FERNET_KEY)
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://frontend.test")


@pytest.fixture(autouse=True)
def _no_egress(monkeypatch):
    for module_name, attr in EGRESS_SITES:
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, attr, _STUBS[attr])


@pytest_asyncio.fixture(scope="module")
async def world(tmp_path_factory) -> AsyncGenerator[World, None]:
    previous = settings.UPLOAD_DIR
    upload_dir = tmp_path_factory.mktemp("uploads")
    settings.UPLOAD_DIR = str(upload_dir)
    built = await build_world(upload_dir)
    try:
        yield built
    finally:
        try:
            await drop_world(built)
        finally:
            settings.UPLOAD_DIR = previous


@pytest_asyncio.fixture
async def fresh_world(tmp_path_factory) -> AsyncGenerator[World, None]:
    previous = settings.UPLOAD_DIR
    upload_dir = tmp_path_factory.mktemp("uploads")
    settings.UPLOAD_DIR = str(upload_dir)
    built = await build_world(upload_dir)
    try:
        yield built
    finally:
        try:
            await drop_world(built)
        finally:
            settings.UPLOAD_DIR = previous


@pytest.fixture
def as_user(accounts, signing_key, authz_client) -> Callable[[WorldUser], Awaitable[AsyncClient]]:
    async def make(user: WorldUser) -> AsyncClient:
        accounts.add(user.uid, user.email)
        token = mint_id_token(signing_key, uid=user.uid, email=user.email)
        return await authz_client(token)

    return make
