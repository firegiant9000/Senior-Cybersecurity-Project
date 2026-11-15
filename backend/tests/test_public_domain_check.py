"""Service-level tests for the public, DNS-only domain check."""

from __future__ import annotations

import logging
import socket
import ssl

import dns.exception
import dns.resolver
import httpx
import pytest
import pytest_asyncio

from app.core.config import settings
from app.core.limiter import limiter
from app.services import public_domain_check
from app.services.public_domain_check import EXPLANATIONS, check_public_domain

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


async def test_undecodable_second_dmarc_record_still_counts(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=reject", b"v=DMARC1; p=none\xff"])
    result = await check_public_domain(HOST)
    assert result.dmarc_found is False
    assert result.rating == "spoofable"


async def test_dkim_is_never_queried(fake_resolver):
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=none"])
    await check_public_domain(HOST)
    assert fake_resolver.calls
    assert all("_domainkey" not in qname for qname, _ in fake_resolver.calls)


# --- API -----------------------------------------------------------------------

URL = "/api/v1/public/domain-check"
BAD_HOST_DETAIL = "Enter a domain name such as example.com."


@pytest_asyncio.fixture
async def flag_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "ENABLE_PUBLIC_READINESS", True)
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def ok_resolver(fake_resolver: FakeResolver) -> FakeResolver:
    fake_resolver.set("victim-co.com", [SPF])
    fake_resolver.set("_dmarc.victim-co.com", ["v=DMARC1; p=reject"])
    fake_resolver.set(HOST, [SPF])
    fake_resolver.set(DMARC_HOST, ["v=DMARC1; p=none"])
    return fake_resolver


JSON_HEADERS = {"content-type": "application/json"}


@pytest.mark.parametrize(
    "content",
    [b'{"domain": "example.com"}', b'{"domain": "1.2.3.4"}', b'{"nope": 1}', b"{bad"],
)
async def test_flag_off_returns_404(client, monkeypatch, fake_resolver, content):
    monkeypatch.setattr(settings, "ENABLE_PUBLIC_READINESS", False)
    resp = await client.post(URL, content=content, headers=JSON_HEADERS)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}
    assert fake_resolver.calls == []


async def test_ok_response_shape(client, flag_on, ok_resolver):
    resp = await client.post(URL, json={"domain": "victim-co.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == {
        "status",
        "spf_found",
        "dmarc_found",
        "dmarc_policy",
        "rating",
        "explanation",
    }
    assert data["status"] == "ok"
    assert data["rating"] == "protected"
    assert data["explanation"] == EXPLANATIONS["protected"]
    assert "v=spf1" not in resp.text
    assert "v=DMARC1" not in resp.text
    assert "victim-co" not in resp.text


@pytest.mark.parametrize(
    ("answer", "status"),
    [(dns.resolver.NXDOMAIN(), "domain_not_found"), (dns.exception.Timeout(), "unavailable")],
)
async def test_not_found_and_unavailable_have_no_rating(
    client, flag_on, fake_resolver, answer, status
):
    fake_resolver.set(HOST, answer)
    resp = await client.post(URL, json={"domain": HOST})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == status
    assert data["rating"] is None
    assert data["spf_found"] is None
    assert data["explanation"] == EXPLANATIONS[status]


@pytest.mark.parametrize(
    "domain",
    ["1.2.3.4", "[::1]", "localhost", "https://example.com", "example.com/path"]
    + ["example.com:8080", "a." * 127 + "com", ""],
)
async def test_invalid_hostname_is_422(client, flag_on, fake_resolver, domain):
    resp = await client.post(URL, json={"domain": domain})
    assert resp.status_code == 422
    assert resp.json()["detail"] == BAD_HOST_DETAIL
    assert fake_resolver.calls == []


async def test_extra_field_is_422(client, flag_on, fake_resolver):
    resp = await client.post(URL, json={"domain": "a.com", "x": "victim-co.com"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == BAD_HOST_DETAIL
    assert "victim-co.com" not in resp.text
    assert fake_resolver.calls == []


async def test_overlong_domain_is_422_and_not_echoed(client, flag_on, fake_resolver):
    resp = await client.post(URL, json={"domain": "victim-co" * 200 + ".com"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == BAD_HOST_DETAIL
    assert "victim-co" not in resp.text
    assert fake_resolver.calls == []


@pytest.mark.parametrize(
    "content", [b"{bad", b"[]", b'"x"', b"{}", b'{"domain": 5}', b"\xff\xfe", b""]
)
async def test_malformed_body_is_generic_422(client, flag_on, fake_resolver, content):
    resp = await client.post(URL, content=content, headers=JSON_HEADERS)
    assert resp.status_code == 422
    assert resp.json() == {"detail": BAD_HOST_DETAIL}
    assert fake_resolver.calls == []


async def test_case_and_trailing_dot_share_the_cache(client, flag_on, ok_resolver):
    first = await client.post(URL, json={"domain": "Example.COM."})
    calls_after_first = len(ok_resolver.calls)
    second = await client.post(URL, json={"domain": "example.com"})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls_after_first == 2
    assert len(ok_resolver.calls) == calls_after_first


async def test_rate_limit_returns_429(client, flag_on, ok_resolver):
    for _ in range(10):
        resp = await client.post(URL, json={"domain": HOST})
        assert resp.status_code == 200
    resp = await client.post(URL, json={"domain": HOST})
    assert resp.status_code == 429


async def test_endpoint_opens_no_socket_and_no_http(client, flag_on, ok_resolver, monkeypatch):
    recorded: list = []

    def record(*args, **kwargs):
        recorded.append(args)
        raise OSError("blocked in test")

    async def record_async(*args, **kwargs):
        record(*args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", record)
    monkeypatch.setattr(socket, "create_connection", record)
    monkeypatch.setattr(socket, "getaddrinfo", record)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", record)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", record_async)

    resp = await client.post(URL, json={"domain": HOST})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert recorded == []


async def test_domain_is_not_logged(client, flag_on, fake_resolver, caplog):
    caplog.set_level(logging.DEBUG)
    host = "victim-co.com"
    fake_resolver.set(host, [SPF])
    fake_resolver.set(f"_dmarc.{host}", ["v=DMARC1; p=reject"])
    await client.post(URL, json={"domain": host})

    fake_resolver.set("gone-victim-co.com", dns.resolver.NXDOMAIN())
    await client.post(URL, json={"domain": "gone-victim-co.com"})

    fake_resolver.set("slow-victim-co.com", dns.exception.Timeout())
    await client.post(URL, json={"domain": "slow-victim-co.com"})

    for record in caplog.records:
        assert "victim-co" not in record.getMessage()
        assert "victim-co" not in repr(record.args)
