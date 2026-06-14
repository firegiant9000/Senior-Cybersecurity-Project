"""Agent scan upload payload schema (Month 4 Phase 3 — FROZEN CONTRACT).

This is the wire contract between the Go scanner (Phase 4) and the upload
endpoint. The Phase 3 endpoint and the Phase 4 scanner output BOTH validate
against it via the shared golden fixture (``tests/fixtures/agent_scan_v1.json``);
do not change a field shape without bumping ``schema_version`` and updating both
sides plus the fixture.

Versioning: ``schema_version`` is a string ``"major.minor"``. The endpoint
accepts the versions in ``SUPPORTED_SCHEMA_VERSIONS`` and rejects anything else
with a clear error so an old scanner fails loudly instead of silently dropping
fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Bump (and add to SUPPORTED_SCHEMA_VERSIONS) on any breaking field change.
CURRENT_SCHEMA_VERSION = "1.0"
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})


class ScanHost(BaseModel):
    """The host the scan was collected on. Identity is the org+agent token, not
    the hostname (hostnames collide) — hostname here is descriptive metadata."""

    model_config = ConfigDict(extra="forbid")

    hostname: str = Field(min_length=1, max_length=255)
    os_name: str | None = Field(default=None, max_length=128)
    os_version: str | None = Field(default=None, max_length=128)
    arch: str | None = Field(default=None, max_length=32)
    ip_address: str | None = Field(default=None, max_length=64)


class ScanSoftware(BaseModel):
    """One installed package. vendor+product+version map straight onto
    ``asset_software`` via ``commit_inventory``."""

    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(min_length=1, max_length=255)
    product: str = Field(min_length=1, max_length=255)
    version: str | None = Field(default=None, max_length=255)


class ScanService(BaseModel):
    """A running service (e.g. from systemctl). Persisted as a replace-on-scan
    snapshot on ``assets.services`` and shown in the asset detail."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    state: str | None = Field(default=None, max_length=64)


class ScanPort(BaseModel):
    """A listening port (only when the scanner was run with --include-ports).
    Persisted as a replace-on-scan snapshot on ``assets.listening_ports``; feeds
    the Month 5 internet-exposed-port risk factor."""

    model_config = ConfigDict(extra="forbid")

    port: int = Field(ge=0, le=65535)
    protocol: Literal["tcp", "udp"] = "tcp"
    process: str | None = Field(default=None, max_length=255)


class AgentScanPayload(BaseModel):
    """The full upload body POSTed to ``/inventory/scans``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(description='Wire schema version, e.g. "1.0".')
    scan_id: str = Field(min_length=1, max_length=64, description="UUID for this scan.")
    nonce: str = Field(min_length=1, max_length=128, description="Per-attempt replay nonce.")
    scanner_version: str = Field(
        min_length=1, max_length=32, description='Scanner build, semver "major.minor.patch".'
    )
    host: ScanHost
    software: list[ScanSoftware] = Field(default_factory=list, max_length=50_000)
    services: list[ScanService] = Field(default_factory=list, max_length=50_000)
    ports: list[ScanPort] = Field(default_factory=list, max_length=50_000)


class ScanUploadAccepted(BaseModel):
    """Response to a successful upload — the scan_run id the agent polls."""

    scan_run_id: int
    status: str
    asset_count: int
    software_count: int
