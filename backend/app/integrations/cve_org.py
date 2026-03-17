"""Helpers for enriching CVE data from CVE.org records."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from cachetools import TTLCache  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)

CVE_ORG_API_URL = "https://cveawg.mitre.org/api/cve"

# Reuse a single client across all calls to avoid repeated SSL handshakes
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient()
    return _http_client


@dataclass(slots=True)
class CveOrgEnrichment:
    """Normalized enrichment fields extracted from a CVE.org record."""

    description: str | None = None
    severity_score: float | None = None
    severity_label: str | None = None
    published_date: str | None = None
    last_modified_date: str | None = None
    vendor: str | None = None
    product: str | None = None


# TTLCache: max 2 000 entries, expire after 1 hour.
# Bounded size prevents unbounded memory growth; TTL means transient outages
# self-heal within an hour rather than requiring a process restart.
_enrichment_cache: TTLCache = TTLCache(maxsize=2000, ttl=3600)


def _iso_from_datetime(raw: Any) -> str | None:
    """Convert ISO datetime/date strings to ISO YYYY-MM-DD."""
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw).split("T", 1)[0]).isoformat()
    except ValueError:
        return None


def _normalize_severity_label(label: Any) -> str | None:
    """Normalize severity labels from CVE.org metrics."""
    if label is None:
        return None
    normalized = str(label).strip().lower()
    mapping = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }
    return mapping.get(normalized)


def _score_to_label(score: float | None) -> str | None:
    """Derive a severity label from a CVSS base score."""
    if score is None:
        return None
    if score >= 9.0:
        return "Critical"
    if score >= 7.0:
        return "High"
    if score >= 4.0:
        return "Medium"
    if score > 0:
        return "Low"
    return None


def _extract_description(container: dict[str, Any]) -> str | None:
    """Extract an English description or title from a CNA/ADP container."""
    descriptions = container.get("descriptions")
    if isinstance(descriptions, list):
        for description in descriptions:
            if not isinstance(description, dict):
                continue
            if str(description.get("lang", "")).lower() != "en":
                continue
            value = description.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()
        for description in descriptions:
            if not isinstance(description, dict):
                continue
            value = description.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()

    title = container.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def _extract_vendor_product(container: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract vendor/product from the affected list when available."""
    affected = container.get("affected")
    if not isinstance(affected, list):
        return None, None

    for entry in affected:
        if not isinstance(entry, dict):
            continue
        vendor = entry.get("vendor")
        product = entry.get("product")
        normalized_vendor = vendor.strip() if isinstance(vendor, str) and vendor.strip() else None
        normalized_product = (
            product.strip() if isinstance(product, str) and product.strip() else None
        )
        if normalized_vendor or normalized_product:
            return normalized_vendor, normalized_product
    return None, None


def _extract_cvss(container: dict[str, Any]) -> tuple[float | None, str | None]:
    """Extract the best available CVSS score and label from a container."""
    metrics = container.get("metrics")
    if not isinstance(metrics, list):
        return None, None

    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        for key in ("cvssV4_0", "cvssV3_1", "cvssV3_0", "cvssV2_0"):
            cvss = metric.get(key)
            if not isinstance(cvss, dict):
                continue
            raw_score = cvss.get("baseScore")
            try:
                score = float(raw_score) if raw_score is not None else None
            except (TypeError, ValueError):
                score = None
            if score is not None:
                score = max(0.0, min(score, 10.0))
            label = _normalize_severity_label(cvss.get("baseSeverity")) or _score_to_label(score)
            if score is not None or label is not None:
                return score, label
    return None, None


def extract_cve_org_enrichment(payload: dict[str, Any]) -> CveOrgEnrichment:
    """Normalize the relevant score/date/vendor fields from a CVE.org payload."""
    cve_metadata = payload.get("cveMetadata") if isinstance(payload, dict) else None
    containers = payload.get("containers") if isinstance(payload, dict) else None
    if not isinstance(containers, dict):
        return CveOrgEnrichment()

    candidate_containers: list[dict[str, Any]] = []
    cna = containers.get("cna")
    if isinstance(cna, dict):
        candidate_containers.append(cna)
    adp = containers.get("adp")
    if isinstance(adp, list):
        candidate_containers.extend(entry for entry in adp if isinstance(entry, dict))

    description: str | None = None
    score: float | None = None
    label: str | None = None
    vendor: str | None = None
    product: str | None = None

    for container in candidate_containers:
        if description is None:
            description = _extract_description(container)
        if score is None and label is None:
            score, label = _extract_cvss(container)
        if vendor is None and product is None:
            vendor, product = _extract_vendor_product(container)

    return CveOrgEnrichment(
        description=description,
        severity_score=score,
        severity_label=label,
        published_date=_iso_from_datetime(
            cve_metadata.get("datePublished") if isinstance(cve_metadata, dict) else None
        ),
        last_modified_date=_iso_from_datetime(
            cve_metadata.get("dateUpdated") if isinstance(cve_metadata, dict) else None
        ),
        vendor=vendor,
        product=product,
    )


async def fetch_cve_org_enrichment(cve_id: str, *, timeout: float = 8.0) -> CveOrgEnrichment:
    """Fetch and cache normalized enrichment fields from CVE.org for a CVE ID."""
    normalized_cve_id = cve_id.strip().upper()
    cached = _enrichment_cache.get(normalized_cve_id)
    if cached is not None:
        return cached

    try:
        client = _get_client()
        response = await client.get(f"{CVE_ORG_API_URL}/{normalized_cve_id}", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            _log.debug("CVE.org has no record for %s (404)", normalized_cve_id)
        else:
            _log.warning("CVE.org enrichment failed for %s: %s", normalized_cve_id, exc)
        enrichment = CveOrgEnrichment()
        _enrichment_cache[normalized_cve_id] = enrichment
        return enrichment
    except (httpx.HTTPError, ValueError) as exc:
        _log.warning("CVE.org enrichment failed for %s: %s", normalized_cve_id, exc)
        enrichment = CveOrgEnrichment()
        _enrichment_cache[normalized_cve_id] = enrichment
        return enrichment

    enrichment = extract_cve_org_enrichment(payload if isinstance(payload, dict) else {})
    _enrichment_cache[normalized_cve_id] = enrichment
    return enrichment
