"""Agent scan ingest helpers (Month 4 Phase 3).

Pure transforms between the frozen ``AgentScanPayload`` wire contract and the
existing inventory plumbing: schema-version gating, scanner min-version checks,
flattening the payload onto ``ParsedRow`` rows for ``commit_inventory``, and a
stable hash of the raw body for the scan_run audit trail. No DB access — the
route owns the transaction (mirroring ``import_inventory_csv``).
"""

from __future__ import annotations

import hashlib
import json

from app.schemas.agent_scan import (
    SUPPORTED_SCHEMA_VERSIONS,
    AgentScanPayload,
)
from app.services.inventory_import import ParsedRow


class ScanRejectedError(Exception):
    """Raised for a payload the endpoint refuses (version gates). Carries an
    HTTP status so the route can translate it without a giant if-ladder."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _parse_semver(value: str) -> tuple[int, int, int]:
    """Parse ``"major.minor.patch"`` into a comparable tuple.

    Tolerates a missing patch and trailing pre-release/build suffixes (``-rc1``,
    ``+sha``) by taking the leading numeric run of each of the first three parts.
    Unparseable parts read as 0 so a junk version sorts oldest and is rejected by
    the min-version gate rather than crashing.
    """
    core = value.strip().split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")

    def _int(part: str) -> int:
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        return int(digits) if digits else 0

    nums = [_int(p) for p in parts[:3]]
    nums += [0] * (3 - len(nums))
    return nums[0], nums[1], nums[2]


def assert_schema_supported(schema_version: str) -> None:
    """Reject an unknown/unsupported wire schema version (422)."""
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
        raise ScanRejectedError(
            422,
            f"Unsupported schema_version {schema_version!r}; this server accepts: {supported}.",
        )


def assert_scanner_version_allowed(scanner_version: str, minimum: str) -> None:
    """Reject a scanner older than ``minimum`` (426 Upgrade Required)."""
    if _parse_semver(scanner_version) < _parse_semver(minimum):
        raise ScanRejectedError(
            426,
            f"Scanner version {scanner_version} is below the minimum {minimum}; please upgrade.",
        )


def payload_to_rows(payload: AgentScanPayload) -> list[ParsedRow]:
    """Flatten a scan payload into ``ParsedRow`` rows for ``commit_inventory``.

    One row per software entry (each carrying the host fields so the asset is
    created/refreshed). When the host reports no software we still emit a single
    host-only row so the asset itself lands — mirroring how ``commit_inventory``
    creates an asset per distinct hostname before attaching software.
    """
    host = payload.host
    if not payload.software:
        return [
            ParsedRow(
                hostname=host.hostname,
                ip_address=host.ip_address,
                os_name=host.os_name,
                os_version=host.os_version,
                vendor=None,
                product=None,
                version=None,
                notes=None,
            )
        ]
    return [
        ParsedRow(
            hostname=host.hostname,
            ip_address=host.ip_address,
            os_name=host.os_name,
            os_version=host.os_version,
            vendor=sw.vendor,
            product=sw.product,
            version=sw.version,
            notes=None,
        )
        for sw in payload.software
    ]


def extract_observations(
    payload: AgentScanPayload,
) -> tuple[list[dict] | None, list[dict] | None]:
    """Flatten the scan's services/ports into the JSON shape stored on the asset.

    Returns ``(services, listening_ports)``. A field is ``None`` when the scan
    reported nothing for it (services not collected, or ``--include-ports`` not
    set) so the caller can skip the write and avoid clobbering a previous scan's
    data — these are replace-on-scan snapshots, not history. When a field *is*
    reported it fully replaces the prior value.
    """
    services = (
        [{"name": s.name, "state": s.state} for s in payload.services]
        if payload.services
        else None
    )
    ports = (
        [{"port": p.port, "protocol": p.protocol, "process": p.process} for p in payload.ports]
        if payload.ports
        else None
    )
    return services, ports


def payload_hash(payload: AgentScanPayload) -> str:
    """Stable sha256 of the canonical payload, stored on the scan_run for audit."""
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
