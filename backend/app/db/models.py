"""Database ORM models."""

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class CVE(Base):
    __tablename__ = "cves"

    id: Mapped[int] = mapped_column(primary_key=True)
    cve_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    cvss_score: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[str | None] = mapped_column(String(20))
    published_date: Mapped[Date | None]

    kev: Mapped["KEV"] = relationship(back_populates="cve", uselist=False)


class KEV(Base):
    __tablename__ = "kev_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    cve_id: Mapped[str] = mapped_column(ForeignKey("cves.cve_id"), unique=True)
    vendor: Mapped[str]
    product: Mapped[str]
    due_date: Mapped[Date | None]

    cve: Mapped["CVE"] = relationship(back_populates="kev")


class IC3Incident(Base):
    __tablename__ = "ic3_incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int]
    sector: Mapped[str]
    state: Mapped[str]
    loss_amount: Mapped[float]


class EconomicIndicator(Base):
    __tablename__ = "economic_indicators"

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str]
    smb_count: Mapped[int]
    avg_revenue: Mapped[float]
