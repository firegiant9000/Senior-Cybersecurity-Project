"""Unit tests for the Month 4 Phase 3 agent-scan ingest helpers.

Covers the frozen schema (validation + the golden fixture), schema-version and
scanner-min-version gates, payload→ParsedRow flattening, and the stable payload
hash. The route wiring + replay/auth is covered in ``test_agent_scan_routes.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent_scan import (
    CURRENT_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    AgentScanPayload,
)
from app.services import agent_scan

GOLDEN = Path(__file__).parent / "fixtures" / "agent_scan_v1.json"


def _golden_dict() -> dict:
    return json.loads(GOLDEN.read_text())


# --- frozen contract / golden fixture ----------------------------------------


def test_golden_fixture_validates_against_current_schema():
    payload = AgentScanPayload.model_validate(_golden_dict())
    assert payload.schema_version == CURRENT_SCHEMA_VERSION
    assert payload.host.hostname == "web-01.example.com"
    assert len(payload.software) == 3


def test_payload_rejects_unknown_fields():
    data = _golden_dict()
    data["host"]["secrets"] = "should not be here"
    with pytest.raises(ValidationError):
        AgentScanPayload.model_validate(data)


def test_current_version_is_supported():
    assert CURRENT_SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS


# --- schema-version gate ------------------------------------------------------


def test_assert_schema_supported_accepts_current():
    agent_scan.assert_schema_supported(CURRENT_SCHEMA_VERSION)


def test_assert_schema_supported_rejects_unknown():
    with pytest.raises(agent_scan.ScanRejectedError) as exc:
        agent_scan.assert_schema_supported("99.0")
    assert exc.value.status_code == 422


# --- scanner min-version gate -------------------------------------------------


@pytest.mark.parametrize("version", ["0.1.0", "0.1.1", "1.0.0", "2.5.3"])
def test_scanner_version_allowed_at_or_above_min(version):
    agent_scan.assert_scanner_version_allowed(version, "0.1.0")


@pytest.mark.parametrize("version", ["0.0.9", "0.0.1"])
def test_scanner_version_below_min_rejected_426(version):
    with pytest.raises(agent_scan.ScanRejectedError) as exc:
        agent_scan.assert_scanner_version_allowed(version, "0.1.0")
    assert exc.value.status_code == 426


def test_scanner_version_tolerates_suffixes_and_missing_patch():
    # "1.2-rc1" and "1.2" both parse to (1, 2, 0) and clear a 1.1.0 minimum.
    agent_scan.assert_scanner_version_allowed("1.2-rc1", "1.1.0")
    agent_scan.assert_scanner_version_allowed("1.2", "1.1.0")


# --- payload → rows -----------------------------------------------------------


def test_payload_to_rows_one_row_per_software_carrying_host():
    payload = AgentScanPayload.model_validate(_golden_dict())
    rows = agent_scan.payload_to_rows(payload)
    assert len(rows) == 3
    assert {r.hostname for r in rows} == {"web-01.example.com"}
    assert {r.os_name for r in rows} == {"Ubuntu"}
    assert ("nginx", "nginx", "1.18.0") in {(r.vendor, r.product, r.version) for r in rows}


def test_payload_to_rows_host_only_when_no_software():
    data = _golden_dict()
    data["software"] = []
    payload = AgentScanPayload.model_validate(data)
    rows = agent_scan.payload_to_rows(payload)
    assert len(rows) == 1
    assert rows[0].hostname == "web-01.example.com"
    assert rows[0].vendor is None and rows[0].product is None


# --- observations (services / ports) -----------------------------------------


def test_extract_observations_maps_services_and_ports():
    payload = AgentScanPayload.model_validate(_golden_dict())
    services, ports = agent_scan.extract_observations(payload)
    assert services == [
        {"name": "nginx.service", "state": "running"},
        {"name": "ssh.service", "state": "running"},
    ]
    assert ports == [
        {"port": 443, "protocol": "tcp", "process": "nginx"},
        {"port": 22, "protocol": "tcp", "process": "sshd"},
    ]


def test_extract_observations_none_when_not_reported():
    # A scan run without --include-ports (and with services collection failing)
    # reports empty lists; the helper returns None so the caller skips the write
    # and never clobbers a prior scan's data.
    data = _golden_dict()
    data["services"] = []
    data["ports"] = []
    payload = AgentScanPayload.model_validate(data)
    services, ports = agent_scan.extract_observations(payload)
    assert services is None
    assert ports is None


# --- payload hash -------------------------------------------------------------


def test_payload_hash_is_stable_and_order_independent():
    a = AgentScanPayload.model_validate(_golden_dict())
    # Reorder software — canonical (sorted-key) JSON hashing is field-stable, and
    # the same logical payload should hash identically regardless of dict order.
    data = _golden_dict()
    b = AgentScanPayload.model_validate(data)
    assert agent_scan.payload_hash(a) == agent_scan.payload_hash(b)
    assert len(agent_scan.payload_hash(a)) == 64


def test_payload_hash_changes_with_content():
    a = AgentScanPayload.model_validate(_golden_dict())
    data = _golden_dict()
    data["host"]["hostname"] = "different-host"
    b = AgentScanPayload.model_validate(data)
    assert agent_scan.payload_hash(a) != agent_scan.payload_hash(b)
