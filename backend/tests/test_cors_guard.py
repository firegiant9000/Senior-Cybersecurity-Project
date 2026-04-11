"""Tests for CORS production guard in Settings."""

import pytest
from pydantic import ValidationError


def _make_settings(**overrides):
    """Build a Settings instance with the minimum required fields."""
    from app.core.config import Settings

    base = {
        "DATABASE_URL": "postgresql+asyncpg://user:pw@localhost:5432/db",
        **overrides,
    }
    return Settings(**base)


def test_cors_localhost_blocked_in_production():
    """Settings must reject localhost CORS origins when APP_ENV=production."""
    with pytest.raises((ValueError, ValidationError)):
        _make_settings(
            APP_ENV="production",
            CORS_ORIGINS=["http://localhost:5173"],
        )


def test_cors_localhost_allowed_in_development():
    """Settings should accept localhost origins in development."""
    settings = _make_settings(
        APP_ENV="development",
        CORS_ORIGINS=["http://localhost:5173"],
    )
    assert "http://localhost:5173" in settings.CORS_ORIGINS


def test_cors_localhost_allowed_in_testing():
    """Settings should accept localhost origins in testing."""
    settings = _make_settings(
        APP_ENV="testing",
        CORS_ORIGINS=["http://localhost:5173"],
    )
    assert "http://localhost:5173" in settings.CORS_ORIGINS


def test_cors_production_domain_allowed_in_production():
    """Settings must accept a production domain when APP_ENV=production."""
    settings = _make_settings(
        APP_ENV="production",
        CORS_ORIGINS=["https://hacker-tracker-75f91.web.app"],
    )
    assert settings.CORS_ORIGINS == ["https://hacker-tracker-75f91.web.app"]


def test_cors_empty_origins_allowed_in_production():
    """Empty CORS_ORIGINS is valid in production (no requests allowed, fail-fast)."""
    settings = _make_settings(APP_ENV="production", CORS_ORIGINS=[])
    assert settings.CORS_ORIGINS == []
