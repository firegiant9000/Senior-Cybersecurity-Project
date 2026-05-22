"""Core configuration and settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator

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

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        """Render (and some other hosts) provide postgres:// which SQLAlchemy
        does not accept.  Normalise to the required postgresql+asyncpg:// scheme."""
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            pass  # already correct
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.DATABASE_URL = url
        return self

    # Logging
    LOG_LEVEL: str = "DEBUG"
    # JSON logs default off so local devs see readable output. Production /
    # staging deployments set LOG_JSON=true via env so log aggregators get
    # structured JSON.
    LOG_JSON: bool = False

    # Observability (Sentry)
    SENTRY_DSN: str = ""  # empty disables Sentry entirely (safe default for dev/tests)
    SENTRY_ENVIRONMENT: str = ""  # defaults to APP_ENV when blank
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0  # 0.0 disables performance tracing
    SENTRY_RELEASE: str = ""  # optional, e.g., git SHA injected at deploy time

    # Frontend
    FRONTEND_URL: str = ""  # must be set explicitly per environment
    CORS_ORIGINS: list[str] = []  # must be set explicitly per environment

    @model_validator(mode="after")
    def _validate_production_cors(self) -> "Settings":
        if self.APP_ENV not in ("development", "testing"):
            localhost_origins = [o for o in self.CORS_ORIGINS if "localhost" in o]
            if localhost_origins:
                raise ValueError(
                    f"CORS_ORIGINS contains localhost entries {localhost_origins} "
                    f"but APP_ENV={self.APP_ENV!r}. "
                    "Set CORS_ORIGINS to production domains only."
                )
        return self

    # Auth (Firebase — service account key path is set via GOOGLE_APPLICATION_CREDENTIALS env var)
    SECRET_KEY: str = "change-me-in-production"  # retained for non-auth signing if needed
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    FIREBASE_PROJECT_ID: str = ""

    # External API Keys for Data Ingestion
    NVD_API_KEY: str = ""
    CENSUS_API_KEY: str = ""
    BEA_API_KEY: str = ""

    # Domain intelligence
    HIBP_API_KEY: str = ""  # Have I Been Pwned domain search (paid, optional)
    SHODAN_API_KEY: str = ""  # Shodan host lookup — 100 free credits/month
    OTX_API_KEY: str = ""  # AlienVault OTX threat intel (free registration)

    # AI / LLM
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    AI_SUMMARY_ENABLED: bool = True
    AI_SUMMARY_CACHE_TTL: int = 3600  # seconds (1 hour)

    # Ingestion
    FORCE_SEED: bool = False

    # Ingestion scheduling — cron expressions (standard 5-field format, empty = disabled)
    # Examples: "0 */6 * * *" = every 6 hours, "0 2 * * 0" = weekly Sunday 2am
    INGEST_SCHEDULE_NVD: str = ""
    INGEST_SCHEDULE_KEV: str = ""
    INGEST_SCHEDULE_IC3: str = ""
    INGEST_SCHEDULE_ECONOMICS: str = ""
    # Maximum seconds a run may be "running" before it is considered stale/timed-out
    INGEST_LOCK_TIMEOUT_SECONDS: int = 3600
    # Number of automatic retries on failure (exponential back-off: 30s, 120s)
    INGEST_MAX_RETRIES: int = 2
    # Set to False to disable the in-process scheduler (useful when running multiple instances)
    SCHEDULER_ENABLED: bool = True
    # Staleness thresholds in hours — source is "stale" if last successful run exceeds this age
    INGEST_STALE_HOURS_NVD: int = 25
    INGEST_STALE_HOURS_KEV: int = 25
    INGEST_STALE_HOURS_IC3: int = 168
    INGEST_STALE_HOURS_ECON: int = 168

    # Rate limiting
    RATE_LIMIT_AUTH: str = "30/minute"
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
    ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
