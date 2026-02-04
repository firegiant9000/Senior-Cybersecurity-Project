"""Models module initialization."""

from app.models.base import Base
from app.models.ingest_run import IngestRun

__all__ = ["Base", "IngestRun"]
