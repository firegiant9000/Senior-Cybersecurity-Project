"""Tests for CVE.org enrichment helpers."""

from app.integrations.cve_org import extract_cve_org_enrichment


def test_extract_cve_org_enrichment_reads_cvss_dates_and_affected_product() -> None:
    """CVE.org payloads should yield normalized score, label, dates, and product info."""
    payload = {
        "cveMetadata": {
            "cveId": "CVE-2025-68613",
            "datePublished": "2025-12-19T22:23:47.777Z",
            "dateUpdated": "2026-03-12T03:55:15.270Z",
        },
        "containers": {
            "cna": {
                "title": "n8n Vulnerable to Remote Code Execution via Expression Injection",
                "descriptions": [
                    {
                        "lang": "en",
                        "value": "n8n contains a critical remote code execution vulnerability.",
                    }
                ],
                "metrics": [
                    {
                        "cvssV3_1": {
                            "baseScore": 10,
                            "baseSeverity": "CRITICAL",
                            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H",
                        }
                    }
                ],
                "affected": [
                    {
                        "vendor": "n8n-io",
                        "product": "n8n",
                    }
                ],
            }
        },
    }

    enrichment = extract_cve_org_enrichment(payload)

    assert enrichment.description == "n8n contains a critical remote code execution vulnerability."
    assert enrichment.severity_score == 10.0
    assert enrichment.severity_label == "Critical"
    assert enrichment.published_date == "2025-12-19"
    assert enrichment.last_modified_date == "2026-03-12"
    assert enrichment.vendor == "n8n-io"
    assert enrichment.product == "n8n"


def test_extract_cve_org_enrichment_handles_missing_metrics() -> None:
    """Missing CVSS blocks should not break enrichment parsing."""
    payload = {
        "cveMetadata": {
            "cveId": "CVE-2024-0001",
            "datePublished": "2024-01-01T00:00:00Z",
        },
        "containers": {
            "cna": {
                "title": "Fallback title",
                "affected": [{"vendor": "example", "product": "widget"}],
            }
        },
    }

    enrichment = extract_cve_org_enrichment(payload)

    assert enrichment.description == "Fallback title"
    assert enrichment.severity_score is None
    assert enrichment.severity_label is None
    assert enrichment.published_date == "2024-01-01"
    assert enrichment.vendor == "example"
    assert enrichment.product == "widget"
