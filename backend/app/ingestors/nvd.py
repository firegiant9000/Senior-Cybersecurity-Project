# app/ingestors/nvd.py
"""NVD CVE ingestion with full pagination support and data normalization."""
import logging
from datetime import date

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import CVE
from app.schemas.validators import NvdCveValidationSchema

logger = logging.getLogger(__name__)

NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


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
        # Try CVSS v3.1, then v3.0, then v2.0
        cvss_v3 = (
            cve_data["metrics"].get("cvssMetricV31")
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
) -> None:
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

                existing = await db.execute(select(CVE).where(CVE.cve_id == cve_id))
                if existing.scalar_one_or_none() is not None:
                    continue

                cve = CVE(
                    cve_id=cve_id,
                    description=description,
                    cvss_score=cvss_score,
                    severity=severity,
                    published_date=published_date,
                )
                db.add(cve)
                total_fetched += 1
                total_validated += 1

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
