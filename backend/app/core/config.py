"""Core configuration and settings."""
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings  # type: ignore[import-not-found]  # pylint: disable=import-error
except ImportError:  # pragma: no cover - fallback for older environments
    from pydantic import BaseSettings  # type: ignore


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Application
    APP_NAME: str = "Cyber Threat Intelligence Platform"
    APP_ENV: str = "development"
    API_PREFIX: str = "/api/v1"

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cyber_threat_db"

    # Logging
    LOG_LEVEL: str = "DEBUG"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # Feature flags
    ENABLE_DEMO_MODE: bool = True

    class Config:
        """Pydantic settings configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
