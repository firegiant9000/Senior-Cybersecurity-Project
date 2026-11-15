"""Service-level tests for the public, DNS-only domain check."""

from __future__ import annotations

import dns.exception
import dns.resolver
import pytest

from app.services import public_domain_check
from app.services.public_domain_check import check_public_domain

HOST = "example.com"
DMARC_HOST = f"_dmarc.{HOST}"
SPF = "v=spf1 include:_spf.example.net ~all"


class _FakeTxt:
    def __init__(self, text: str | bytes) -> None:
        self.strings = (text if isinstance(text, bytes) else text.encode(),)


class FakeResolver:
    """Maps (qname, "TXT") to a list of TXT strings or an exception instance."""

    def __init__(self) -> None:
        self.answers: dict[tuple[str, str], list[str | bytes] | Exception] = {}
        self.calls: list[tuple[str, str]] = []

    def set(self, qname: str, value: list[str | bytes] | Exception) -> None:
        self.answers[(qname, "TXT")] = value

    async def resolve(self, qname: str, rdtype: str):
        self.calls.append((qname, rdtype))
        value = self.answers.get((qname, rdtype), dns.resolver.NXDOMAIN())
        if isinstance(value, Exception):
            raise value
        return [_FakeTxt(t) for t in value]


@pytest.fixture
def fake_resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver()
    monkeypatch.setattr(public_domain_check, "_make_resolver", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _clear_cache():
    public_domain_check._cache.clear()
    yield
    public_domain_check._cache.clear()


@pytest.mark.parametrize(
    ("record", "policy", "rating"),
    [
        ("v=DMARC1; p=reject", "reject", "protected"),
        ("v=DMARC1; p=quarantine", "quarantine", "protected"),
        ("v=DMARC1; p=none", "none", "monitoring_only"),
    ],
)
async def test_rating_for_each_policy(fake_resolver, record, policy, rating):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, [record])
    result = await check_public_domain(HOST)
    assert result.status == "ok"
    assert result.spf_found is True
    assert result.dmarc_found is True
    assert result.dmarc_policy == policy
    assert result.rating == rating


async def test_no_dmarc_is_spoofable(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, dns.resolver.NXDOMAIN())
    result = await check_public_domain(HOST)
    assert result.rating == "spoofable"
    assert result.dmarc_found is False


async def test_dmarc_no_answer_is_spoofable(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, dns.resolver.NoAnswer())
    result = await check_public_domain(HOST)
    assert result.rating == "spoofable"
    assert result.dmarc_found is False


async def test_enforcing_dmarc_without_spf_is_protected(fake_resolver):
    fake_resolver.set(HOST, dns.resolver.NoAnswer())
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=reject"])
    result = await check_public_domain(HOST)
    assert result.rating == "protected"
    assert result.spf_found is False


async def test_nxdomain_is_domain_not_found_without_rating(fake_resolver):
    fake_resolver.set(HOST, dns.resolver.NXDOMAIN())
    result = await check_public_domain(HOST)
    assert result.status == "domain_not_found"
    assert result.rating is None
    assert result.spf_found is None
    assert all(qname != DMARC_HOST for qname, _ in fake_resolver.calls)


@pytest.mark.parametrize("failing", [HOST, DMARC_HOST])
@pytest.mark.parametrize("exc", [dns.exception.Timeout, dns.resolver.NoNameservers])
async def test_timeout_is_unavailable_without_rating(fake_resolver, failing, exc):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=reject"])
    fake_resolver.set(failing, exc())
    result = await check_public_domain(HOST)
    assert result.status == "unavailable"
    assert result.rating is None
    assert result.spf_found is None
    assert result.dmarc_found is None
    assert result.dmarc_policy is None


async def test_unavailable_is_not_cached(fake_resolver):
    fake_resolver.set(HOST, dns.exception.Timeout())
    first = await check_public_domain(HOST)
    assert first.status == "unavailable"
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=reject"])
    second = await check_public_domain(HOST)
    assert second.status == "ok"


async def test_second_check_makes_no_dns_query(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=reject"])
    first = await check_public_domain(HOST)
    calls_after_first = len(fake_resolver.calls)
    second = await check_public_domain(HOST)
    assert second == first
    assert len(fake_resolver.calls) == calls_after_first


async def test_dmarc_without_valid_policy_is_monitoring_only(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; rua=mailto:x@y"])
    result = await check_public_domain(HOST)
    assert result.dmarc_found is True
    assert result.dmarc_policy is None
    assert result.rating == "monitoring_only"


async def test_two_dmarc_records_is_spoofable(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=reject", "v=DMARC1; p=none"])
    result = await check_public_domain(HOST)
    assert result.dmarc_found is False
    assert result.rating == "spoofable"


async def test_non_utf8_apex_txt_is_skipped(fake_resolver):
    fake_resolver.set(HOST, [b"\xff\xfe", SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=reject"])
    result = await check_public_domain(HOST)
    assert result.status == "ok"
    assert result.spf_found is True
    assert result.rating == "protected"


async def test_non_utf8_dmarc_txt_is_skipped(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, [b"\xff\xfe", "v=DMARC1; p=reject"])
    result = await check_public_domain(HOST)
    assert result.status == "ok"
    assert result.dmarc_found is True
    assert result.dmarc_policy == "reject"
    assert result.rating == "protected"


async def test_dkim_is_never_queried(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=none"])
    await check_public_domain(HOST)
    assert fake_resolver.calls
    assert all("_domainkey" not in qname for qname, _ in fake_resolver.calls)
