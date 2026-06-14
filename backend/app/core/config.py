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
    # NVD CPE configurations (per-CVE affected version ranges → cve_cpe_match).
    # Persist CPE criteria during NVD CVE ingest; disable to keep ingest lean.
    NVD_CPE_PERSIST_ON_INGEST: bool = True
    # Backfill skips CVEs whose CPE rows are newer than this; commits per batch.
    NVD_CPE_CACHE_TTL_HOURS: int = 168
    NVD_CPE_BATCH_SIZE: int = 50
    # Max CVEs the scheduled CPE backfill sweep processes per run. Bounds NVD
    # load (each CVE = one rate-limited request) so the existing corpus is
    # backfilled incrementally over successive runs rather than in one burst.
    NVD_CPE_BACKFILL_MAX_PER_RUN: int = 500
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
    # EPSS runs daily by default, after NVD (02:00 UTC) so scores cover the freshest CVE set.
    INGEST_SCHEDULE_EPSS: str = "0 2 * * *"
    # Month 3 Phase 4: background CPE-matcher sweep. Runs after the EPSS refresh
    # so recomputed findings pick up the freshest scores. The inline triggers on
    # CSV import / M365 sync cover the real-time path; this backstops them.
    MATCHER_SCHEDULE: str = "30 2 * * *"
    # Month 3 Phase 1 tail: scheduled CPE backfill for the pre-existing CVE
    # corpus (CVEs ingested before version-criteria capture landed). Runs after
    # the nightly NVD window; the TTL skip makes it converge then no-op. Empty
    # disables it (the inline persist-on-ingest still covers new CVEs).
    NVD_CPE_BACKFILL_SCHEDULE: str = "0 4 * * *"
    # Month 4 Phase 7: retention sweep. Ages out scan history past the time window
    # (with a per-org safety ceiling), ages out audit_log rows past the 365-day
    # window, and purges expired replay nonces. Runs after the nightly matcher
    # sweep so it never deletes a run mid-recompute. Empty disables.
    RETENTION_SWEEP_SCHEDULE: str = "0 5 * * *"
    # Primary scan-history retention: keep runs newer than this. Sized for the
    # month-over-month report comparison (needs >= 13 months of history).
    SCAN_RUN_RETENTION_DAYS: int = 400
    # Safety ceiling on scan_runs kept per org regardless of age, so a pathological
    # upload loop can't grow the table without bound. NOT the primary policy — the
    # time window above is. Set high so multi-host scanner orgs keep full history.
    MAX_SCAN_RUNS_PER_ORG: int = 2000
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
    INGEST_STALE_HOURS_EPSS: int = 49

    # Rate limiting
    RATE_LIMIT_AUTH: str = "30/minute"
    RATE_LIMIT_DATA: str = "60/minute"

    # Agent trust model (Month 4 Phase 1 — frozen in docs/month_4_phase0_closeout.md).
    # Default token lifetime; per-org override is a future enhancement.
    AGENT_TOKEN_DEFAULT_EXPIRY_DAYS: int = 365
    # Rotation keeps the old token valid for this long so live hosts don't break.
    AGENT_TOKEN_ROTATION_GRACE_HOURS: int = 24
    # Agents with no contact for this long are surfaced as stale in the admin UI.
    AGENT_INACTIVE_AFTER_DAYS: int = 30
    # Scanner upload endpoint (Month 4 Phase 3).
    # Per-token rate limit applied to POST /inventory/scans (keyed by token prefix).
    RATE_LIMIT_AGENT_UPLOAD: str = "12/minute"
    # Reject scan payloads from scanners older than this (semver, "major.minor.patch").
    MIN_AGENT_VERSION: str = "0.1.0"
    # Reject a re-submitted (scan_id, nonce) pair seen within this window.
    AGENT_SCAN_REPLAY_WINDOW_HOURS: int = 24

    # M365 / Entra OAuth integration (Phase E spike — see docs/m365_integration_notes.md)
    # Feature-flagged off in prod; the frontend reads ENABLE_M365_INTEGRATION via the
    # public-config endpoint and hides the card when false.
    ENABLE_M365_INTEGRATION: bool = False
    M365_CLIENT_ID: str = ""
    M365_CLIENT_SECRET: str = ""
    M365_AUTHORITY: str = "https://login.microsoftonline.com/common"
    M365_REDIRECT_URI: str = ""
    # Fernet key (urlsafe base64, 32 bytes). Generated once per env with
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
    # Stored credentials are unrecoverable if this key is lost — rotate by re-consent.
    M365_FERNET_KEY: str = ""

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
