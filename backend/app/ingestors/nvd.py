# app/ingestors/nvd.py
"""NVD CVE ingestion with full pagination support and data normalization."""

import asyncio
import logging
from collections.abc import Callable
from datetime import date

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import CVE
from app.schemas.validators import NvdCveValidationSchema

logger = logging.getLogger(__name__)

NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _should_update_cve(existing: CVE, *, today: date | None = None) -> bool:
    """Return whether an existing CVE row should be refreshed from NVD."""
    if existing.cvss_score is None or existing.severity is None:
        return True
    if existing.published_date is None:
        return True
    return bool(today and existing.published_date > today)


def _apply_normalized_cve(
    existing: CVE,
    *,
    description: str,
    cvss_score: float | None,
    severity: str | None,
    published_date: date | None,
    max_published_date: date | None = None,
) -> bool:
    """Update an existing CVE row from normalized NVD data when values changed."""
    changed = False

    effective_published = published_date
    if max_published_date and effective_published and effective_published > max_published_date:
        effective_published = max_published_date

    if existing.description != description:
        existing.description = description
        changed = True
    if existing.cvss_score != cvss_score:
        existing.cvss_score = cvss_score
        changed = True
    if existing.severity != severity:
        existing.severity = severity
        changed = True
    if existing.published_date != effective_published:
        existing.published_date = effective_published
        changed = True

    return changed


async def upsert_normalized_cve(
    db: AsyncSession,
    *,
    cve_id: str,
    description: str,
    cvss_score: float | None,
    severity: str | None,
    published_date: date | None,
    max_published_date: date | None = None,
) -> tuple[str, bool]:
    """Insert or update a normalized NVD CVE row.

    Returns a tuple of (`inserted`|`updated`|`unchanged`, changed_flag).
    """
    existing = (await db.execute(select(CVE).where(CVE.cve_id == cve_id))).scalar_one_or_none()

    effective_published = published_date
    if max_published_date and effective_published and effective_published > max_published_date:
        effective_published = max_published_date

    if existing is None:
        try:
            async with db.begin_nested():
                db.add(
                    CVE(
                        cve_id=cve_id,
                        description=description,
                        cvss_score=cvss_score,
                        severity=severity,
                        published_date=effective_published,
                    )
                )
                await db.flush()
            return "inserted", True
        except IntegrityError:
            # Another ingestor inserted this CVE concurrently — fetch and update it.
            existing = (
                await db.execute(select(CVE).where(CVE.cve_id == cve_id))
            ).scalar_one_or_none()
            if existing is None:
                return "unchanged", False

    changed = _apply_normalized_cve(
        existing,
        description=description,
        cvss_score=cvss_score,
        severity=severity,
        published_date=published_date,
        max_published_date=max_published_date,
    )
    if changed:
        return "updated", True
    return "unchanged", False


async def fetch_nvd_cve_by_id(
    cve_id: str,
    *,
    api_key: str | None = None,
    timeout: float = 30.0,
) -> dict | None:
    """Fetch a single CVE payload from the official NVD API by CVE ID."""
    params = {"cveId": cve_id}
    use_api_key = bool(api_key)
    retries_remaining = 3

    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            headers: dict[str, str] = {}
            if use_api_key and api_key:
                headers["apiKey"] = api_key

            try:
                response = await client.get(NVD_URL, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
                break
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 429 and retries_remaining > 0:
                    retries_remaining -= 1
                    wait_seconds = 2 ** (3 - retries_remaining)
                    await asyncio.sleep(wait_seconds)
                    continue
                if status_code == 429:
                    logger.warning(
                        "NVD lookup rate-limited for %s after retries; skipping",
                        cve_id,
                    )
                    return None
                if use_api_key and status_code == 403:
                    logger.warning(
                        "NVD lookup for %s returned %s with API key; retrying without key",
                        cve_id,
                        status_code,
                    )
                    use_api_key = False
                    continue
                if status_code == 404:
                    logger.debug("NVD lookup missing upstream record for %s", cve_id)
                    return None
                raise

    vulnerabilities = payload.get("vulnerabilities", [])
    if not vulnerabilities:
        return None
    return vulnerabilities[0].get("cve", {})


async def backfill_missing_nvd_fields_for_existing_cves(  # noqa: C901
    db: AsyncSession,
    *,
    cve_ids: list[str] | None = None,
    limit: int | None = None,
    max_published_date: date | None = None,
    commit_every: int = 25,
    progress_callback: Callable[[dict[str, int]], None] | None = None,
) -> dict[str, int]:
    """Backfill existing CVEs that are missing NVD-derived fields.

    This is primarily used for KEV-created placeholder rows that predate NVD ingestion.
    """
    settings = get_settings()
    stmt = select(CVE).where(
        (CVE.cvss_score.is_(None)) | (CVE.severity.is_(None)) | (CVE.published_date.is_(None))
    )
    if cve_ids:
        stmt = stmt.where(CVE.cve_id.in_(cve_ids))
    stmt = stmt.order_by(CVE.cve_id.asc())
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = (await db.execute(stmt)).scalars().all()
    results = {"checked": 0, "updated": 0, "unchanged": 0, "missing_upstream": 0}
    per_request_delay_seconds = 1.2 if settings.NVD_API_KEY else 2.0
    total_rows = len(rows)

    if progress_callback is not None:
        progress_callback({**results, "total": total_rows})

    for row in rows:
        results["checked"] += 1
        cve_payload = await fetch_nvd_cve_by_id(
            row.cve_id,
            api_key=settings.NVD_API_KEY,
        )
        if cve_payload is None:
            results["missing_upstream"] += 1
            if commit_every > 0 and results["checked"] % commit_every == 0:
                await db.commit()
                if progress_callback is not None:
                    progress_callback({**results, "total": total_rows})
            await asyncio.sleep(per_request_delay_seconds)
            continue

        normalized = _normalize_nvd_cve(cve_payload)
        if normalized is None:
            results["missing_upstream"] += 1
            if commit_every > 0 and results["checked"] % commit_every == 0:
                await db.commit()
                if progress_callback is not None:
                    progress_callback({**results, "total": total_rows})
            await asyncio.sleep(per_request_delay_seconds)
            continue

        cve_id, description, cvss_score, severity, published_date = normalized
        status, _ = await upsert_normalized_cve(
            db,
            cve_id=cve_id,
            description=description,
            cvss_score=cvss_score,
            severity=severity,
            published_date=published_date,
            max_published_date=max_published_date,
        )
        if status == "updated":
            results["updated"] += 1
        else:
            results["unchanged"] += 1

        if commit_every > 0 and results["checked"] % commit_every == 0:
            await db.commit()
            if progress_callback is not None:
                progress_callback({**results, "total": total_rows})

        await asyncio.sleep(per_request_delay_seconds)

    await db.commit()
    if progress_callback is not None:
        progress_callback({**results, "total": total_rows})
    return results


def _normalize_nvd_cve(  # noqa: C901
    cve_data: dict,
) -> tuple[str, str, float | None, str | None, date | None] | None:
    """Normalize and validate raw NVD CVE data.

    Args:
        cve_data: Raw CVE data dict from NVD API

    Returns:
        Tuple of (cve_id, description, cvss_score, severity, published_date)
        or None if validation fails

    Normalization rules:
    - CVE ID is uppercased
    - Description defaults to "No description available" if missing/empty
    - CVSS score is clamped to [0.0, 10.0], None if missing
    - Severity is normalized to known labels or None
    - Published date is parsed to ISO format or None
    """
    cve_id = cve_data.get("id", "").strip().upper()
    if not cve_id:
        logger.warning("CVE record missing ID; skipping")
        return None

    # Extract description (default if missing)
    description = "No description available"
    if cve_data.get("descriptions"):
        desc_list = cve_data["descriptions"]
        if isinstance(desc_list, list) and desc_list:
            desc_val = desc_list[0].get("value", "").strip()
            if desc_val:
                description = desc_val

    # Extract CVSS score and severity (with normalization)
    cvss_score = None
    severity = None
    if "metrics" in cve_data and isinstance(cve_data["metrics"], dict):
        # Try CVSS v4.0, then v3.1, then v3.0, then v2.0
        cvss_v3 = (
            cve_data["metrics"].get("cvssMetricV40")
            or cve_data["metrics"].get("cvssMetricV31")
            or cve_data["metrics"].get("cvssMetricV30")
            or cve_data["metrics"].get("cvssMetricV2")
        )
        if cvss_v3:
            cvss_data_list = cvss_v3 if isinstance(cvss_v3, list) else [cvss_v3]
            if cvss_data_list:
                cvss_obj = cvss_data_list[0].get("cvssData", {})
                raw_score = cvss_obj.get("baseScore")
                raw_severity = cvss_obj.get("baseSeverity")

                # Normalize score to [0.0, 10.0]
                if raw_score is not None:
                    try:
                        cvss_score = float(raw_score)
                        cvss_score = max(0.0, min(cvss_score, 10.0))
                    except (TypeError, ValueError):
                        logger.warning(
                            "Invalid CVSS score %r for %s; treating as None",
                            raw_score,
                            cve_id,
                        )
                        cvss_score = None

                # Normalize severity label
                if raw_severity:
                    severity_upper = str(raw_severity).strip().upper()
                    if severity_upper in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
                        severity = severity_upper.capitalize()
                    else:
                        logger.warning(
                            "Unknown severity label %r for %s; treating as None",
                            raw_severity,
                            cve_id,
                        )
                        severity = None

    # Extract published date (ISO format)
    published_date = None
    if cve_data.get("published"):
        pub_str = str(cve_data["published"]).strip()
        try:
            # Handle ISO datetime or date strings
            if "T" in pub_str:
                pub_str = pub_str.split("T")[0]  # Extract date part
            parsed = date.fromisoformat(pub_str)
            published_date = parsed
        except ValueError:
            logger.warning("Invalid published date %r for %s; treating as None", pub_str, cve_id)

    # Validate using Pydantic schema
    try:
        validated = NvdCveValidationSchema(
            cve_id=cve_id,
            description=description,
            cvss_score=cvss_score,
            severity=severity,
            published_date=published_date.isoformat() if published_date else None,
        )
        return (
            validated.cve_id,
            validated.description,
            validated.cvss_score,
            validated.severity,
            published_date,
        )
    except ValidationError as e:
        logger.warning("NVD CVE validation failed for %s: %s", cve_id, e)
        return None


async def ingest_nvd(  # noqa: C901
    db: AsyncSession, start_index: int = 0, max_results: int | None = None
) -> int:
    """
    Ingest CVEs from NVD API with pagination support and data normalization.

    Args:
        db: Database session
        start_index: Starting index for pagination (default 0)
        max_results: Maximum number of CVEs to ingest (None = all available)

    Applies normalization to:
    - CVSS scores (clamped to [0.0, 10.0])
    - Severity labels (standardized to Critical, High, Medium, Low, or None)
    - Descriptions (default provided if missing)
    - Published dates (parsed to ISO format or None)
    """
    # Local import avoids a circular dependency (nvd_cpe imports fetch_nvd_cve_by_id).
    from app.ingestors.nvd_cpe import persist_cpe_configurations

    settings = get_settings()
    api_key = settings.NVD_API_KEY

    use_api_key = bool(api_key)
    if use_api_key:
        logger.info("NVD ingestion: API key detected; attempting authenticated requests")
    else:
        logger.info("NVD ingestion: no API key configured; using unauthenticated requests")

    total_fetched = 0
    total_validated = 0
    current_index = start_index
    reached_limit = False
    aligned_to_latest_window = False

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            params = {
                "startIndex": current_index,
                "resultsPerPage": 2000,  # Max allowed per request
            }
            headers: dict[str, str] = {}
            if use_api_key and api_key:
                headers["apiKey"] = api_key

            try:
                resp = await client.get(NVD_URL, params=params, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if use_api_key and status_code in {403, 404}:
                    logger.warning(
                        "NVD returned %s with API key; retrying without API key",
                        status_code,
                    )
                    use_api_key = False
                    continue
                if status_code == 429:
                    logger.warning(
                        "NVD rate limited at index %s. Committing %s CVEs fetched so far.",
                        current_index,
                        total_fetched,
                    )
                    break
                raise

            data = resp.json()

            # NVD API returns oldest records first at startIndex=0.
            # If caller requests a bounded max_results from index 0,
            # jump to the latest window so dashboard reflects current CVEs.
            if (
                max_results
                and start_index == 0
                and current_index == 0
                and not aligned_to_latest_window
            ):
                total_results = int(data.get("totalResults", 0))
                latest_start = max(total_results - max_results, 0)
                if latest_start > 0:
                    current_index = latest_start
                    aligned_to_latest_window = True
                    continue
                aligned_to_latest_window = True

            vulnerabilities = data.get("vulnerabilities", [])
            if not vulnerabilities:
                break

            for item in vulnerabilities:
                if max_results and total_validated >= max_results:
                    reached_limit = True
                    break

                cve_data = item["cve"]
                normalized = _normalize_nvd_cve(cve_data)
                if normalized is None:
                    logger.debug("Skipped invalid CVE: %s", cve_data.get("id"))
                    continue

                cve_id, description, cvss_score, severity, published_date = normalized

                status, changed = await upsert_normalized_cve(
                    db,
                    cve_id=cve_id,
                    description=description,
                    cvss_score=cvss_score,
                    severity=severity,
                    published_date=published_date,
                )
                if status == "inserted":
                    total_fetched += 1
                if changed:
                    total_validated += 1

                if settings.NVD_CPE_PERSIST_ON_INGEST:
                    # Capture the full CPE criteria (version ranges) NVD publishes
                    # alongside the CVE so the matcher can do version-aware matching.
                    await persist_cpe_configurations(db, cve_id=cve_id, cve=cve_data)

            await db.commit()

            if reached_limit:
                break

            # Check if there are more results
            total_results = data.get("totalResults", 0)
            current_index += 2000
            if current_index >= total_results:
                break

            print(
                f"Fetched {total_fetched} CVEs, validated {total_validated} "
                f"(Total available: {total_results})"
            )

    logger.info("NVD ingestion complete: %d fetched, %d validated", total_fetched, total_validated)
    return total_validated
