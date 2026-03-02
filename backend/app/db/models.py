"""Database ORM models."""
from __future__ import annotations

# pylint: disable=too-few-public-methods,unsubscriptable-object
from datetime import date

from sqlalchemy import (  # type: ignore[import-not-found]  # pylint: disable=import-error
    Date,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import (  # type: ignore[import-not-found]  # pylint: disable=import-error
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base


class CVE(Base):
    """NVD CVE record."""

    __tablename__ = "cves"

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    cve_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    kev: Mapped[KEV] = relationship(back_populates="cve", uselist=False)


class KEV(Base):
    """CISA Known Exploited Vulnerabilities catalog entry."""

    __tablename__ = "kev_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    cve_id: Mapped[str] = mapped_column(ForeignKey("cves.cve_id"), unique=True)
    vendor: Mapped[str] = mapped_column(String(255))
    product: Mapped[str] = mapped_column(String(255))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    cve: Mapped[CVE] = relationship(back_populates="kev")


class IC3Incident(Base):
    """IC3 incident record for historical impact signals."""

    __tablename__ = "ic3_incidents"

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    year: Mapped[int]
    sector: Mapped[str]
    state: Mapped[str]
    loss_amount: Mapped[float]


class EconomicIndicator(Base):
    """Economic indicator for risk context."""

    __tablename__ = "economic_indicators"

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    state: Mapped[str]
    smb_count: Mapped[int]
    avg_revenue: Mapped[float]
