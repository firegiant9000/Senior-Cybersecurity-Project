"""OpenAPI docs exposure (Task 13): off in production, on in development and testing."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings as real_settings
from app.core.security_headers import API_CSP

DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def _create_app_for(app_env: str):
    """Build a fresh app under patched settings, as tests/test_secret_key_guard.py does."""
    env_settings = real_settings.model_copy(
        update={"APP_ENV": app_env, "SECRET_KEY": "test-only-secret-key-not-the-default-0123"}
    )
    with patch("app.main.settings", env_settings):
        from app.main import create_app

        return create_app()


@pytest.mark.parametrize("path", DOCS_PATHS)
async def test_docs_disabled_in_production(path):
    app = _create_app_for("production")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(path)

    assert resp.status_code == 404


@pytest.mark.parametrize("path", DOCS_PATHS + ("/docs/oauth2-redirect",))
async def test_docs_404_in_production_carries_api_csp(path):
    app = _create_app_for("production")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(path)

    assert resp.status_code == 404
    assert resp.headers["content-security-policy"] == API_CSP


@pytest.mark.parametrize("path", DOCS_PATHS)
async def test_docs_enabled_in_development(path):
    app = _create_app_for("development")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(path)

    assert resp.status_code == 200
