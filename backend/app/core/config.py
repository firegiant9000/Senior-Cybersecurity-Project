"""Core configuration and settings."""

from functools import lru_cache
from pathlib import Path

try:
    from pydantic_settings import (
        BaseSettings,  # type: ignore[import-not-found]  # pylint: disable=import-error
    )
except ImportError:  # pragma: no cover - fallback for older environments
    from pydantic import BaseSettings  # type: ignore


class Settings(BaseSettings):  # type: ignore[reportGeneralTypeIssues]
    """Application settings from environment variables."""

    # Pydantic v2-style settings config; using a plain dict keeps type checkers happy.
    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "allow",
    }

    # Application
    APP_NAME: str = "Cyber Threat Intelligence Platform"
    APP_ENV: str = "development"
    API_PREFIX: str = "/api/v1"

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # Database
    DATABASE_URL: str

    # Logging
    LOG_LEVEL: str = "DEBUG"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
    ]

    # Auth (Firebase — service account key path is set via GOOGLE_APPLICATION_CREDENTIALS env var)
    SECRET_KEY: str = "change-me-in-production"  # retained for non-auth signing if needed

    # Feature flags
    ENABLE_DEMO_MODE: bool = False

    # External API Keys for Data Ingestion
    NVD_API_KEY: str = ""
    CENSUS_API_KEY: str = ""
    BEA_API_KEY: str = ""

    # Ingestion
    FORCE_SEED: bool = False

    # Rate limiting
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_DATA: str = "60/minute"

    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_UPLOAD_TYPES: list[str] = [
        "text/csv",
        "application/pdf",
        "text/plain",
        "application/json",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
