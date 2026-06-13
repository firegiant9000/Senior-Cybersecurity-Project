"""CSV inventory import service.

Parses uploaded CSV bytes into validated rows, upserts assets +
asset_software within a single transaction, and runs a literal
vendor+product KEV match against the existing CISA catalog. The
matcher returns the number of KEV hits so the scan_run metadata can
surface "your inventory has N KEV-listed packages" without waiting on
the Month 3 CPE matcher.

Per `docs/month_2_execution_plan.md` C6 + risk R3, this is a
preliminary literal match; the UI must label results accordingly.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.asset import Asset
from app.db.asset_software import AssetSoftware
from app.db.models import KEV

logger = logging.getLogger(__name__)

MAX_CSV_ROWS = 10_000
REQUIRED_COLUMNS = ("hostname",)
KNOWN_COLUMNS = (
    "hostname",
    "ip_address",
    "os_name",
    "os_version",
    "vendor",
    "product",
    "version",
    "notes",
)


@dataclass
class ParsedRow:
    """One validated CSV row."""

    hostname: str
    ip_address: str | None
    os_name: str | None
    os_version: str | None
    vendor: str | None
    product: str | None
    version: str | None
    notes: str | None


@dataclass
class ParseResult:
    """Outcome of parsing a CSV body."""

    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    # Distinct counts for the preview UI.
    distinct_assets: int = 0
    distinct_software: int = 0

    @property
    def valid_rows(self) -> int:
        return len(self.rows)

    @property
    def invalid_rows(self) -> int:
        return len(self.errors)


def _norm(value: str | None) -> str | None:
    """Trim and collapse internal whitespace; empty → None."""
    if value is None:
        return None
    s = " ".join(value.strip().split())
    return s or None


def _validate_ip(value: str | None) -> tuple[str | None, str | None]:
    """Return (cleaned, error or None). Empty IP is allowed."""
    if not value:
        return None, None
    try:
        ipaddress.ip_address(value)
        return value, None
    except ValueError:
        return value, f"invalid ip_address {value!r}"


def parse_csv(text: str) -> ParseResult:
    """Parse a CSV body into validated rows.

    Validates required columns, IP addresses, hostname length, and the
    10 000-row cap. Duplicate (hostname, vendor, product, version)
    tuples within the same upload are dropped with a warning.
    """
    result = ParseResult()
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        result.errors.append(
            {
                "row_number": 1,
                "errors": [f"Missing required columns: {', '.join(missing)}"],
            }
        )
        return result

    seen: set[tuple[str, str, str, str]] = set()
    distinct_hosts: set[str] = set()

    for i, raw in enumerate(reader, start=2):  # row 1 is header
        if len(result.rows) >= MAX_CSV_ROWS:
            result.errors.append(
                {
                    "row_number": i,
                    "errors": [f"Exceeded maximum of {MAX_CSV_ROWS} rows — remaining rows skipped"],
                }
            )
            break

        hostname = _norm(raw.get("hostname"))
        if not hostname:
            result.errors.append({"row_number": i, "errors": ["missing hostname"]})
            continue
        if len(hostname) > 255:
            result.errors.append({"row_number": i, "errors": ["hostname exceeds 255 characters"]})
            continue

        ip_raw = _norm(raw.get("ip_address"))
        ip_value, ip_err = _validate_ip(ip_raw)
        row_errors: list[str] = []
        if ip_err:
            # Don't drop the row for a bad IP — store as-is, warn the user.
            row_errors.append(ip_err)

        vendor = _norm(raw.get("vendor"))
        product = _norm(raw.get("product"))
        if (vendor and not product) or (product and not vendor):
            result.errors.append(
                {
                    "row_number": i,
                    "errors": ["vendor and product must both be set or both empty"],
                }
            )
            continue

        dedup = (
            hostname.lower(),
            (vendor or "").lower(),
            (product or "").lower(),
            (raw.get("version") or "").strip().lower(),
        )
        if dedup in seen:
            result.errors.append(
                {
                    "row_number": i,
                    "errors": ["duplicate of an earlier row — skipped"],
                }
            )
            continue
        seen.add(dedup)

        distinct_hosts.add(hostname.lower())

        if row_errors:
            # Soft warning, but still keep the row.
            result.errors.append({"row_number": i, "errors": row_errors})

        result.rows.append(
            ParsedRow(
                hostname=hostname,
                ip_address=ip_value,
                os_name=_norm(raw.get("os_name")),
                os_version=_norm(raw.get("os_version")),
                vendor=vendor,
                product=product,
                version=_norm(raw.get("version")),
                notes=_norm(raw.get("notes")),
            )
        )

    result.distinct_assets = len(distinct_hosts)
    result.distinct_software = sum(1 for r in result.rows if r.vendor and r.product)
    return result


async def commit_inventory(  # noqa: C901
    session: AsyncSession,
    *,
    org_id: int,
    rows: list[ParsedRow],
    scan_run_id: int | None = None,
    source: str = "csv_upload",
) -> tuple[int, int]:
    """Upsert assets + asset_software for an org. Returns (assets, software) counts.

    Idempotent by (org_id, hostname): existing rows have ``last_seen`` and
    selected fields refreshed instead of being duplicated. Software is
    deduplicated by (org_id, asset_id, vendor, product, version) — matching
    rows refresh ``last_seen``; new rows are inserted.

    ``source`` labels the provenance on new ``assets.discovered_via`` /
    ``asset_software.source`` rows (e.g. ``"csv_upload"`` or ``"m365"``) so the
    same upsert path serves both onboarding entry points.

    Caller is responsible for the surrounding transaction commit (this
    function only flushes).
    """
    # Map hostname → existing Asset.
    hostnames = sorted({r.hostname for r in rows})
    existing_assets: dict[str, Asset] = {}
    if hostnames:
        result = await session.execute(
            select(Asset).where(Asset.org_id == org_id, Asset.hostname.in_(hostnames))
        )
        for asset in result.scalars().all():
            existing_assets[asset.hostname] = asset

    asset_count = 0
    software_count = 0
    now = func.now()

    # First pass: ensure an Asset row per distinct hostname.
    hostname_to_asset: dict[str, Asset] = dict(existing_assets)
    seen_hosts: set[str] = set()
    for row in rows:
        if row.hostname in seen_hosts:
            continue
        seen_hosts.add(row.hostname)
        existing = hostname_to_asset.get(row.hostname)
        if existing is None:
            asset = Asset(
                org_id=org_id,
                hostname=row.hostname,
                ip_address=row.ip_address,
                os_name=row.os_name,
                os_version=row.os_version,
                discovered_via=source,
                is_active=True,
                created_by_scan_run_id=scan_run_id,
            )
            session.add(asset)
            hostname_to_asset[row.hostname] = asset
            asset_count += 1
        else:
            # Refresh nice-to-have fields if newer info is in the CSV.
            if row.ip_address:
                existing.ip_address = row.ip_address
            if row.os_name:
                existing.os_name = row.os_name
            if row.os_version:
                existing.os_version = row.os_version
            existing.is_active = True
            existing.last_seen = now  # type: ignore[assignment]
            asset_count += 1  # touched
    await session.flush()  # assign IDs to newly inserted assets

    # Second pass: software rows. Skip rows without vendor+product.
    sw_rows = [r for r in rows if r.vendor and r.product]
    if not sw_rows:
        return asset_count, 0

    asset_ids = {hostname_to_asset[r.hostname].id for r in sw_rows}
    # Fetch existing software for these assets so we can dedup.
    existing_sw_by_key: dict[tuple[int, str, str, str], AssetSoftware] = {}
    if asset_ids:
        result = await session.execute(
            select(AssetSoftware).where(
                AssetSoftware.org_id == org_id,
                AssetSoftware.asset_id.in_(asset_ids),
            )
        )
        for sw in result.scalars().all():
            key = (
                sw.asset_id,
                sw.vendor.lower(),
                sw.product.lower(),
                (sw.version or "").lower(),
            )
            existing_sw_by_key[key] = sw

    touched_keys: set[tuple[int, str, str, str]] = set()
    for row in sw_rows:
        asset = hostname_to_asset[row.hostname]
        key = (
            asset.id,
            (row.vendor or "").lower(),
            (row.product or "").lower(),
            (row.version or "").lower(),
        )
        if key in touched_keys:
            # Already inserted or refreshed in this upload.
            continue
        touched_keys.add(key)
        existing_sw = existing_sw_by_key.get(key)
        if existing_sw is None:
            session.add(
                AssetSoftware(
                    asset_id=asset.id,
                    org_id=org_id,
                    vendor=row.vendor,
                    product=row.product,
                    version=row.version,
                    source=source,
                    created_by_scan_run_id=scan_run_id,
                )
            )
            software_count += 1
        else:
            existing_sw.last_seen = now  # type: ignore[assignment]
            software_count += 1

    await session.flush()
    return asset_count, software_count


async def count_kev_matches(session: AsyncSession, org_id: int) -> int:
    """Count distinct asset_software rows whose (vendor, product) appears in KEV.

    Case-insensitive literal match — Month 2 placeholder for the real CPE
    matcher landing in Month 3 (see R3).
    """
    kev_pairs = await session.execute(
        select(func.lower(KEV.vendor), func.lower(KEV.product)).distinct()
    )
    pairs = {(row[0], row[1]) for row in kev_pairs.all()}
    if not pairs:
        return 0

    result = await session.execute(
        select(
            func.lower(AssetSoftware.vendor),
            func.lower(AssetSoftware.product),
            func.count(AssetSoftware.id),
        )
        .where(AssetSoftware.org_id == org_id)
        .group_by(func.lower(AssetSoftware.vendor), func.lower(AssetSoftware.product))
    )
    total = 0
    for vendor, product, count in result.all():
        if (vendor, product) in pairs:
            total += int(count)
    return total


__all__ = [
    "MAX_CSV_ROWS",
    "ParsedRow",
    "ParseResult",
    "commit_inventory",
    "count_kev_matches",
    "parse_csv",
]
