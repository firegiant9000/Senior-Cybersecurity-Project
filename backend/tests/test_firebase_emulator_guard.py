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
    return Settings(_env_file=None, **base)


def test_emulator_allowed_in_development():
    settings = _make_settings(
        APP_ENV="development", FIREBASE_AUTH_EMULATOR_HOST="firebase-auth:9099"
    )
    assert settings.FIREBASE_AUTH_EMULATOR_HOST == "firebase-auth:9099"


@pytest.mark.parametrize("app_env", ["testing", "production"])
@pytest.mark.parametrize("host", ["localhost:9099", " "])
def test_emulator_rejected_outside_development(app_env, host):
    """Whitespace counts: firebase-admin treats any non-empty value as emulator mode."""
    with pytest.raises((ValueError, ValidationError), match="FIREBASE_AUTH_EMULATOR_HOST"):
        _make_settings(APP_ENV=app_env, FIREBASE_AUTH_EMULATOR_HOST=host)


def test_emulator_read_from_environment(monkeypatch):
    """The SDK reads the real env var, so the guard must see it there too."""
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    with pytest.raises((ValueError, ValidationError), match="FIREBASE_AUTH_EMULATOR_HOST"):
        _make_settings(APP_ENV="production")


def test_emulator_mode_only_answers_loopback_hosts(monkeypatch):
    """Unsigned tokens are accepted in emulator mode, so a DNS-rebound host must be refused."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    client = TestClient(create_app())  # no context manager: lifespan (DB, Firebase) not run
    # An unrouted path: the host check runs before routing, and nothing touches the
    # shared DB/health engines from this client's event loop.
    path = "/__host-check-probe"
    assert client.get(path, headers={"host": "attacker.example:8000"}).status_code == 400
    assert client.get(path, headers={"host": "localhost:8000"}).status_code == 404


def test_non_emulator_mode_has_no_host_restriction(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    client = TestClient(create_app())
    assert client.get("/__host-check-probe", headers={"host": "api.example.com"}).status_code == 404


def test_production_without_emulator_is_fine(monkeypatch):
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    settings = _make_settings(APP_ENV="production")
    assert settings.FIREBASE_AUTH_EMULATOR_HOST == ""
