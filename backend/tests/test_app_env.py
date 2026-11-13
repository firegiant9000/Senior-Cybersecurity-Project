"""APP_ENV is required and fails closed (T-PLAT-03)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DB_URL = "postgresql+asyncpg://u:p@localhost:5432/db"


def test_app_env_missing_fails(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL=DB_URL, _env_file=None)


def test_app_env_unknown_value_fails(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL=DB_URL, APP_ENV="staging", _env_file=None)


def test_app_env_production_is_not_dev_or_test(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    s = Settings(DATABASE_URL=DB_URL, APP_ENV="production", _env_file=None)
    assert s.is_dev_or_test is False


def test_app_env_testing_is_dev_or_test(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    s = Settings(DATABASE_URL=DB_URL, APP_ENV="testing", _env_file=None)
    assert s.is_dev_or_test is True
