# app/ingestors/cisa_kev.py
"""Ingest CISA Known Exploited Vulnerabilities into cves and kev_catalog.

Includes data validation and normalization to ensure consistency.
"""

import asyncio
import logging
from datetime import date

import httpx  # type: ignore[import-not-found]  # pylint: disable=import-error
from pydantic import ValidationError
from sqlalchemy import select  # type: ignore[import-not-found]  # pylint: disable=import-error
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # type: ignore[import-not-found]  # pylint: disable=import-error
)

from app.db.models import CVE, KEV
from app.integrations.cve_org import fetch_cve_org_enrichment
from app.schemas.validators import CisaKevValidationSchema

logger = logging.getLogger(__name__)

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


def _parse_date(value: str | None) -> date | None:
    """Parse YYYY-MM-DD string to date, or return None."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        logger.warning("Invalid date format: %r", value)
        return None


def _normalize_cisa_kev(item: dict) -> tuple[str, str, str, date | None] | None:
    """Normalize and validate raw CISA KEV data.

    Args:
        item: Raw KEV record from CISA API

    Returns:
        Tuple of (cve_id, vendor, product, kev_date_added) or None if validation fails

    Normalization rules:
    - CVE ID is uppercased and validated to match CVE-YYYY-NNNNN format
    - Vendor is trimmed and required to be non-empty
    - Product is trimmed and required to be non-empty
    - KEV date added is parsed to ISO format or None
    """
    try:
        # Extract raw values
        cve_id = item.get("cveID", "").strip()
        vendor = (item.get("vendorProject") or "").strip()
        product = (item.get("product") or "").strip()
        # API provides both dateAdded and dueDate; the dashboard column is
        # "Date Added", so persist that value for response consistency.
        date_added_str = item.get("dateAdded")

        # Get short description with fallback
        description = (
            item.get("shortDescription")
            or item.get("vulnerabilityName")
            or "CISA known exploited vulnerability"
        )
        description = description.strip() if description else "CISA known exploited vulnerability"

        # Validate using Pydantic schema
        validated = CisaKevValidationSchema(
            cve_id=cve_id,
            vendor=vendor,
            product=product,
            due_date=date_added_str,
        )

        kev_date_added = _parse_date(validated.due_date) if validated.due_date else None

        return (
            validated.cve_id,
            validated.vendor,
            validated.product,
            kev_date_added,
        )

    except ValidationError as e:
        logger.warning("CISA KEV validation failed for %s: %s", item.get("cveID"), e)
        return None


async def ingest_cisa_kev(db: AsyncSession) -> int:  # noqa: C901
    """
    Fetch CISA KEV catalog and upsert into cves (stub) and kev_catalog.

    Applies validation and normalization to all records.


    Returns:
        The number of new KEV entries ingested (not including updates)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(CISA_KEV_URL)
        resp.raise_for_status()
        data = resp.json()

    count = 0
    total_processed = 0
    total_validated = 0
    # Track CVE rows that were newly created and need enrichment
    new_cve_ids: list[str] = []

    for item in data["vulnerabilities"]:
        total_processed += 1

        # Normalize and validate raw KEV data
        normalized = _normalize_cisa_kev(item)
        if normalized is None:
            logger.debug("Skipped invalid KEV: %s", item.get("cveID"))
            continue

        cve_id, vendor, product, kev_date_added = normalized
        total_validated += 1

        # Get or create CVE record
        result = await db.execute(select(CVE).where(CVE.cve_id == cve_id))
        cve = result.scalar_one_or_none()
        if cve is None:
            description = (
                item.get("shortDescription")
                or item.get("vulnerabilityName")
                or "CISA known exploited vulnerability"
            )
            db.add(
                CVE(
                    cve_id=cve_id,
                    description=description,
                    cvss_score=None,
                    severity=None,
                    published_date=None,
                )
            )
            await db.flush()  # so KEV insert can satisfy FK to cves.cve_id
            new_cve_ids.append(cve_id)

        # Upsert KEV: update if exists, else add.
        result = await db.execute(select(KEV).where(KEV.cve_id == cve_id))
        kev = result.scalar_one_or_none()
        if kev is None:
            db.add(
                KEV(
                    cve_id=cve_id,
                    vendor=vendor,
                    product=product,
                    due_date=kev_date_added,
                )
            )
            count += 1
        else:
            kev.vendor = vendor
            kev.product = product
            kev.due_date = kev_date_added

    # Enrich newly-created CVE placeholder rows from CVE.org before committing.
    # This eliminates per-row API calls at query time (N+1 problem).
    if new_cve_ids:
        logger.info("Enriching %d new CVE rows from CVE.org", len(new_cve_ids))
        semaphore = asyncio.Semaphore(8)

        async def _fetch_enrichment(cve_id: str):
            """Fetch CVE.org enrichment (network I/O only, no DB access)."""
            async with semaphore:
                return cve_id, await fetch_cve_org_enrichment(cve_id)

        # Fetch all enrichments concurrently (network-bound), then apply DB
        # updates sequentially to avoid concurrent use of the shared AsyncSession.
        enrichments = await asyncio.gather(*(_fetch_enrichment(cid) for cid in new_cve_ids))
        for cve_id, enrichment in enrichments:
            if not any(
                [enrichment.severity_score, enrichment.severity_label, enrichment.published_date]
            ):
                continue
            row_result = await db.execute(select(CVE).where(CVE.cve_id == cve_id))
            row = row_result.scalar_one_or_none()
            if row is None:
                continue
            if enrichment.description and not row.description:
                row.description = enrichment.description
            if enrichment.severity_score is not None and row.cvss_score is None:
                row.cvss_score = enrichment.severity_score
            if enrichment.severity_label and row.severity is None:
                row.severity = enrichment.severity_label
            if enrichment.published_date and row.published_date is None:
                try:
                    row.published_date = date.fromisoformat(enrichment.published_date)
                except ValueError:
                    pass
        logger.info("CVE.org enrichment complete for %d rows", len(new_cve_ids))

    await db.commit()
    logger.info(
        "CISA KEV ingest complete: %s new entries, %s validated, %s total processed",
        count,
        total_validated,
        total_processed,
    )
    return count
