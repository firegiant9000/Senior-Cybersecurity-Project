"""Tests for search and filter functionality across all table endpoints."""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# NVD CVE filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nvd_cves_no_filters(client: AsyncClient) -> None:
    """Baseline: NVD endpoint still works without any filters."""
    response = await client.get("/api/v1/nvd/cves", params={"page_size": "5"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_nvd_cves_search_filter(client: AsyncClient) -> None:
    """Search filter narrows results to CVEs matching the query."""
    response = await client.get(
        "/api/v1/nvd/cves",
        params={"search": "CVE-2021", "page_size": "10"},
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert "CVE-2021" in item["id"].upper()


@pytest.mark.asyncio
async def test_nvd_cves_severity_filter(client: AsyncClient) -> None:
    """Severity filter returns only matching severity labels."""
    for severity in ("Critical", "High", "Medium", "Low", "Unknown"):
        response = await client.get(
            "/api/v1/nvd/cves",
            params={"severity": severity, "page_size": "5"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            # NVD _score_to_label returns None for null scores; the filter
            # maps "Unknown" to cvss_score IS NULL, so None label is expected.
            if severity == "Unknown":
                assert item["severity_label"] in (None, "Unknown")
            else:
                assert item["severity_label"] == severity


@pytest.mark.asyncio
async def test_nvd_cves_combined_filters(client: AsyncClient) -> None:
    """Search + severity can be combined."""
    response = await client.get(
        "/api/v1/nvd/cves",
        params={"search": "CVE", "severity": "High", "page_size": "5"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_nvd_cves_empty_search_returns_all(client: AsyncClient) -> None:
    """Empty search string should behave like no filter."""
    all_resp = await client.get("/api/v1/nvd/cves", params={"page_size": "5"})
    search_resp = await client.get(
        "/api/v1/nvd/cves", params={"search": "", "page_size": "5"}
    )
    assert all_resp.json()["total"] == search_resp.json()["total"]


# ---------------------------------------------------------------------------
# CISA KEV filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cisa_kev_no_filters(client: AsyncClient) -> None:
    """Baseline: CISA KEV endpoint still works without filters."""
    response = await client.get(
        "/api/v1/vulnerabilities/exploited", params={"page_size": "5"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_cisa_kev_search_filter(client: AsyncClient) -> None:
    """Search filter on CISA KEV narrows by CVE ID."""
    response = await client.get(
        "/api/v1/vulnerabilities/exploited",
        params={"search": "CVE-2021", "page_size": "10"},
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert "CVE-2021" in item["id"].upper()


@pytest.mark.asyncio
async def test_cisa_kev_severity_filter(client: AsyncClient) -> None:
    """Severity filter on CISA KEV returns matching labels."""
    response = await client.get(
        "/api/v1/vulnerabilities/exploited",
        params={"severity": "Critical", "page_size": "5"},
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["severity_label"] == "Critical"


# ---------------------------------------------------------------------------
# IC3 filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ic3_no_filters(client: AsyncClient) -> None:
    """Baseline: IC3 endpoint still works without filters."""
    response = await client.get(
        "/api/v1/ic3/incidents", params={"page_size": "5"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_ic3_attack_type_filter(client: AsyncClient) -> None:
    """Attack type filter returns only matching incidents."""
    response = await client.get(
        "/api/v1/ic3/incidents",
        params={"attack_type": "Phishing", "page_size": "10"},
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["attack_type"] == "Phishing"


@pytest.mark.asyncio
async def test_ic3_state_filter(client: AsyncClient) -> None:
    """State filter returns only matching state."""
    response = await client.get(
        "/api/v1/ic3/incidents",
        params={"state": "CA", "page_size": "10"},
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["state"] == "CA"


@pytest.mark.asyncio
async def test_ic3_year_filter(client: AsyncClient) -> None:
    """Year filter returns only matching year."""
    response = await client.get(
        "/api/v1/ic3/incidents",
        params={"year": "2023", "page_size": "10"},
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["year"] == 2023


@pytest.mark.asyncio
async def test_ic3_combined_filters(client: AsyncClient) -> None:
    """Multiple IC3 filters can be combined."""
    response = await client.get(
        "/api/v1/ic3/incidents",
        params={"attack_type": "Phishing", "state": "CA", "year": "2023", "page_size": "5"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_ic3_filter_options_endpoint(client: AsyncClient) -> None:
    """Filter options endpoint returns expected structure."""
    response = await client.get("/api/v1/ic3/filter-options")
    assert response.status_code == 200
    data = response.json()
    assert "attack_types" in data
    assert "states" in data
    assert "years" in data
    assert isinstance(data["attack_types"], list)
    assert isinstance(data["states"], list)
    assert isinstance(data["years"], list)


# ---------------------------------------------------------------------------
# Economics filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_economics_no_filters(client: AsyncClient) -> None:
    """Baseline: Economics endpoint still works without filters."""
    response = await client.get(
        "/api/v1/economics/indicators", params={"page_size": "5"}
    )
    # May return 502 if BEA API is unavailable in test env, which is acceptable
    assert response.status_code in (200, 502)


@pytest.mark.asyncio
async def test_economics_search_filter(client: AsyncClient) -> None:
    """Search filter on economics narrows by state name."""
    response = await client.get(
        "/api/v1/economics/indicators",
        params={"search": "California", "page_size": "10"},
    )
    # May return 502 if BEA API is unavailable
    assert response.status_code in (200, 502)
    if response.status_code == 200:
        data = response.json()
        for item in data["items"]:
            assert "california" in item["state"].lower()


# ---------------------------------------------------------------------------
# Filtered total reflects filter (not unfiltered count)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nvd_filtered_total_is_less_than_unfiltered(client: AsyncClient) -> None:
    """When a filter is applied, total should be <= the unfiltered total."""
    all_resp = await client.get("/api/v1/nvd/cves", params={"page_size": "1"})
    filtered_resp = await client.get(
        "/api/v1/nvd/cves",
        params={"search": "CVE-9999-UNLIKELY", "page_size": "1"},
    )
    if all_resp.status_code == 200 and filtered_resp.status_code == 200:
        assert filtered_resp.json()["total"] <= all_resp.json()["total"]
