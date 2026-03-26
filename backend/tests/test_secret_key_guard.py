"""Tests for SECRET_KEY startup guard."""

from unittest.mock import patch

import pytest


def test_default_secret_key_blocks_production():
    """App must refuse to start when SECRET_KEY is default in production."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.SECRET_KEY = "change-me-in-production"
        mock_settings.APP_ENV = "production"
        mock_settings.APP_NAME = "Test"
        mock_settings.LOG_LEVEL = "WARNING"
        mock_settings.CORS_ORIGINS = ["http://localhost:5173"]
        mock_settings.API_PREFIX = "/api/v1"
        mock_settings.SERVER_HOST = "0.0.0.0"
        mock_settings.SERVER_PORT = 8000
        mock_settings.FORCE_SEED = False

        with pytest.raises(SystemExit, match="FATAL"):
            from app.main import create_app

            create_app()


def test_default_secret_key_allows_development():
    """App should start (with warning) when SECRET_KEY is default in development."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.SECRET_KEY = "change-me-in-production"
        mock_settings.APP_ENV = "development"
        mock_settings.APP_NAME = "Test"
        mock_settings.LOG_LEVEL = "WARNING"
        mock_settings.CORS_ORIGINS = ["http://localhost:5173"]
        mock_settings.API_PREFIX = "/api/v1"
        mock_settings.SERVER_HOST = "0.0.0.0"
        mock_settings.SERVER_PORT = 8000
        mock_settings.FORCE_SEED = False

        from app.main import create_app

        app = create_app()
        assert app is not None


def test_default_secret_key_allows_testing():
    """App should start when SECRET_KEY is default in testing environment."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.SECRET_KEY = "change-me-in-production"
        mock_settings.APP_ENV = "testing"
        mock_settings.APP_NAME = "Test"
        mock_settings.LOG_LEVEL = "WARNING"
        mock_settings.CORS_ORIGINS = ["http://localhost:5173"]
        mock_settings.API_PREFIX = "/api/v1"
        mock_settings.SERVER_HOST = "0.0.0.0"
        mock_settings.SERVER_PORT = 8000
        mock_settings.FORCE_SEED = False

        from app.main import create_app

        app = create_app()
        assert app is not None
