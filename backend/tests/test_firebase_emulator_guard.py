"""Tests for the Firebase Auth emulator guard in Settings."""

import pytest
from pydantic import ValidationError


def _make_settings(**overrides):
    """Build a Settings instance with the minimum required fields."""
    from app.core.config import Settings

    base = {
        "DATABASE_URL": "postgresql+asyncpg://user:pw@localhost:5432/db",
        # Isolate from the production CORS guard (dev containers set a localhost origin).
        "CORS_ORIGINS": [],
        **overrides,
    }
    return Settings(**base)


def test_emulator_allowed_in_development():
    settings = _make_settings(
        APP_ENV="development", FIREBASE_AUTH_EMULATOR_HOST="firebase-auth:9099"
    )
    assert settings.FIREBASE_AUTH_EMULATOR_HOST == "firebase-auth:9099"


@pytest.mark.parametrize("app_env", ["testing", "production"])
def test_emulator_rejected_outside_development(app_env):
    with pytest.raises((ValueError, ValidationError), match="FIREBASE_AUTH_EMULATOR_HOST"):
        _make_settings(APP_ENV=app_env, FIREBASE_AUTH_EMULATOR_HOST="localhost:9099")


def test_emulator_read_from_environment(monkeypatch):
    """The SDK reads the real env var, so the guard must see it there too."""
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    with pytest.raises((ValueError, ValidationError), match="FIREBASE_AUTH_EMULATOR_HOST"):
        _make_settings(APP_ENV="production")


def test_production_without_emulator_is_fine(monkeypatch):
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    settings = _make_settings(APP_ENV="production")
    assert settings.FIREBASE_AUTH_EMULATOR_HOST == ""
