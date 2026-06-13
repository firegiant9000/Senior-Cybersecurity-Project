"""Phase 1 (Month 3) — NVD CPE criteria parser unit tests.

Asserts that version ranges previously discarded by the CVE ingestor are now
captured from NVD CPE configurations, in both the API 2.0 list form and the
legacy dict form.
"""

from __future__ import annotations

from typing import Any

from app.ingestors.nvd_cpe import parse_cpe_configurations

# Log4j (CVE-2021-44228) shaped payload: a version range, not an exact version.
_LOG4J_CVE: dict[str, Any] = {
    "id": "CVE-2021-44228",
    "configurations": [
        {
            "nodes": [
                {
                    "operator": "OR",
                    "negate": False,
                    "cpeMatch": [
                        {
                            "vulnerable": True,
                            "criteria": "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
                            "versionStartIncluding": "2.0",
                            "versionEndExcluding": "2.15.0",
                        }
                    ],
                }
            ]
        }
    ],
}


def test_parses_version_range_from_log4j_payload() -> None:
    criteria = parse_cpe_configurations(_LOG4J_CVE)

    assert len(criteria) == 1
    c = criteria[0]
    assert c["vendor"] == "apache"
    assert c["product"] == "log4j"
    assert c["version_start_including"] == "2.0"
    assert c["version_end_excluding"] == "2.15.0"
    assert c["version_start_excluding"] is None
    assert c["version_end_including"] is None
    assert c["vulnerable"] is True
    assert c["cpe_uri"] == "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*"


def test_parses_legacy_dict_configurations_form() -> None:
    cve = {
        "configurations": {
            "nodes": [
                {
                    "cpeMatch": [
                        {
                            "vulnerable": True,
                            "criteria": "cpe:2.3:a:openssl:openssl:1.0.1:*:*:*:*:*:*:*",
                            "versionEndIncluding": "1.0.1f",
                        }
                    ]
                }
            ]
        }
    }
    criteria = parse_cpe_configurations(cve)

    assert len(criteria) == 1
    assert criteria[0]["product"] == "openssl"
    assert criteria[0]["version_end_including"] == "1.0.1f"


def test_collects_nested_child_nodes_and_multiple_matches() -> None:
    cve = {
        "configurations": [
            {
                "nodes": [
                    {
                        "cpeMatch": [
                            {
                                "vulnerable": True,
                                "criteria": "cpe:2.3:o:linux:linux_kernel:*:*:*:*:*:*:*:*",
                                "versionStartIncluding": "5.0",
                                "versionEndExcluding": "5.10",
                            }
                        ],
                        "children": [
                            {
                                "cpeMatch": [
                                    {
                                        "vulnerable": False,
                                        "criteria": "cpe:2.3:a:vendorx:appy:1.2.3:*:*:*:*:*:*:*",
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }
        ]
    }
    criteria = parse_cpe_configurations(cve)

    assert len(criteria) == 2
    assert criteria[0]["product"] == "linux_kernel"
    assert criteria[0]["vulnerable"] is True
    assert criteria[1]["product"] == "appy"
    assert criteria[1]["vulnerable"] is False


def test_no_configurations_returns_empty() -> None:
    assert parse_cpe_configurations({"id": "CVE-0000-0000"}) == []
    assert parse_cpe_configurations({"configurations": None}) == []
    assert parse_cpe_configurations({}) == []


def test_skips_entries_without_criteria_string() -> None:
    cve = {
        "configurations": [
            {"nodes": [{"cpeMatch": [{"vulnerable": True, "criteria": ""}, {"vulnerable": True}]}]}
        ]
    }
    assert parse_cpe_configurations(cve) == []
