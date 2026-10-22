"""Outbound domain checks only reach public hosts.

The findings engine probes an organization's own domain (headers, TLS, tech
fingerprint). These tests pin the destination rules: a valid public hostname,
every resolved address public, the connection pinned to the checked address,
and each redirect re-checked.
"""

import socket

import httpx
import pytest

from app.services import domain_checks as dc

PUBLIC_V4 = "93.184.216.34"


def _addrinfo(*ips: str):
    out = []
    for ip in ips:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        out.append((family, socket.SOCK_STREAM, 6, "", (ip, 0)))
    return out


@pytest.fixture
def resolve(monkeypatch):
    """Map hostnames to the addresses getaddrinfo returns."""
    table: dict[str, list[str]] = {}

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host not in table:
            raise socket.gaierror("unknown host")
        return _addrinfo(*table[host])

    monkeypatch.setattr(dc.socket, "getaddrinfo", fake_getaddrinfo)
    return table


@pytest.fixture
def http(monkeypatch):
    """Route every outbound HTTP request to a handler; record the requests."""
    state: dict = {"requests": [], "handler": None}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        return state["handler"](request)

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(transport_handler))

    monkeypatch.setattr(dc, "_http_client", factory)
    return state


@pytest.fixture
def no_sockets(monkeypatch):
    calls: list = []

    def fake_create_connection(address, *args, **kwargs):
        calls.append(address)
        raise OSError("blocked in test")

    monkeypatch.setattr(dc.socket, "create_connection", fake_create_connection)
    return calls


# --- hostname rules ----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "example.com"),
        ("Example.COM.", "example.com"),
        ("  www.example.co.uk ", "www.example.co.uk"),
        ("xn--bcher-kva.example", "xn--bcher-kva.example"),
    ],
)
def test_normalize_hostname_accepts_public_style_names(raw, expected):
    assert dc.normalize_hostname(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "localhost",
        "intranet",
        "127.0.0.1",
        "10.0.0.5",
        "[::1]",
        "::1",
        "http://example.com",
        "example.com/path",
        "example.com:8080",
        "user@example.com",
        "a..example.com",
        "-bad.example.com",
        "example.123",
        ("a" * 64) + ".example.com",
        ("abc." * 70) + "com",
    ],
)
def test_normalize_hostname_rejects_non_hostnames(raw):
    assert dc.normalize_hostname(raw) is None


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
    ],
)
def test_is_public_ip_rejects_internal_addresses(ip):
    assert dc.is_public_ip(ip) is False


@pytest.mark.parametrize("ip", [PUBLIC_V4, "1.1.1.1", "2606:4700:4700::1111"])
def test_is_public_ip_accepts_public_addresses(ip):
    assert dc.is_public_ip(ip) is True


def test_resolve_public_ip_refuses_when_any_address_is_internal(resolve):
    resolve["mixed.example.com"] = [PUBLIC_V4, "10.0.0.7"]
    with pytest.raises(dc.UnsafeDestinationError):
        dc.resolve_public_ip("mixed.example.com", 443)


def test_resolve_public_ip_refuses_unresolvable_host(resolve):
    with pytest.raises(dc.UnsafeDestinationError):
        dc.resolve_public_ip("nowhere.example.com", 443)


def test_resolve_public_ip_returns_a_public_address(resolve):
    resolve["ok.example.com"] = [PUBLIC_V4]
    assert dc.resolve_public_ip("ok.example.com", 443) == PUBLIC_V4


# --- HTTP checks -------------------------------------------------------------


async def test_http_check_makes_no_request_to_an_internal_host(resolve, http):
    resolve["internal.example.com"] = ["10.0.0.7"]
    http["handler"] = lambda request: httpx.Response(200)

    result = await dc.check_http_headers("internal.example.com")

    assert http["requests"] == []
    assert result.reachable is False
    assert result.error


async def test_http_check_connects_to_the_checked_address(resolve, http):
    resolve["ok.example.com"] = [PUBLIC_V4]
    http["handler"] = lambda request: httpx.Response(200, headers={"x-frame-options": "DENY"})

    result = await dc.check_http_headers("ok.example.com")

    assert result.reachable is True
    assert result.has_x_frame_options is True
    request = http["requests"][0]
    assert request.url.host == PUBLIC_V4
    assert request.headers["host"] == "ok.example.com"
    assert request.extensions.get("sni_hostname") == "ok.example.com"


async def test_http_check_does_not_follow_a_redirect_to_an_internal_host(resolve, http):
    resolve["ok.example.com"] = [PUBLIC_V4]
    resolve["internal.example.com"] = ["169.254.169.254"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://internal.example.com/latest"})

    http["handler"] = handler

    await dc.check_http_headers("ok.example.com")

    assert all(r.url.host == PUBLIC_V4 for r in http["requests"])


async def test_http_check_does_not_follow_a_redirect_to_an_ip_literal(resolve, http):
    resolve["ok.example.com"] = [PUBLIC_V4]
    http["handler"] = lambda request: httpx.Response(
        301, headers={"location": "http://127.0.0.1:8080/"}
    )

    await dc.check_http_headers("ok.example.com")

    assert all(r.url.host == PUBLIC_V4 for r in http["requests"])


async def test_http_check_follows_a_redirect_to_a_public_host(resolve, http):
    resolve["ok.example.com"] = [PUBLIC_V4]
    resolve["www.example.com"] = ["1.1.1.1"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["host"] == "ok.example.com":
            return httpx.Response(301, headers={"location": "https://www.example.com/"})
        return httpx.Response(200, headers={"strict-transport-security": "max-age=1"})

    http["handler"] = handler

    result = await dc.check_http_headers("ok.example.com")

    assert result.has_hsts is True
    assert [r.url.host for r in http["requests"]] == [PUBLIC_V4, "1.1.1.1"]


async def test_http_check_stops_after_the_redirect_limit(resolve, http):
    resolve["loop.example.com"] = [PUBLIC_V4]
    http["handler"] = lambda request: httpx.Response(
        302, headers={"location": "https://loop.example.com/again"}
    )

    await dc.check_http_headers("loop.example.com")

    # https start plus redirects, then the http fallback plus redirects
    assert len(http["requests"]) <= 2 * (dc._MAX_REDIRECTS + 1)


async def test_tech_fingerprint_makes_no_request_to_an_internal_host(resolve, http):
    resolve["internal.example.com"] = ["192.168.0.10"]
    http["handler"] = lambda request: httpx.Response(200)

    result = await dc.check_tech_fingerprint("internal.example.com")

    assert http["requests"] == []
    assert result.detected == []


# --- TLS check ---------------------------------------------------------------


async def test_ssl_check_opens_no_socket_to_an_internal_host(resolve, no_sockets):
    resolve["internal.example.com"] = ["127.0.0.1"]

    result = await dc.check_ssl("internal.example.com")

    assert no_sockets == []
    assert result.reachable is False
    assert result.error


async def test_ssl_check_connects_to_the_checked_address(resolve, no_sockets):
    resolve["ok.example.com"] = [PUBLIC_V4]

    await dc.check_ssl("ok.example.com")

    assert no_sockets[0] == (PUBLIC_V4, 443)


# --- entry points ------------------------------------------------------------


async def test_tier1_with_an_invalid_hostname_touches_nothing(resolve, http, no_sockets):
    http["handler"] = lambda request: httpx.Response(200)

    dns_r, http_r, ssl_r, tech_r = await dc.run_tier1_checks("127.0.0.1")

    assert http["requests"] == []
    assert no_sockets == []
    assert dns_r.error and http_r.error and ssl_r.error and tech_r.error


async def test_tier2_with_an_invalid_hostname_touches_nothing(http):
    http["handler"] = lambda request: httpx.Response(200)

    results = await dc.run_tier2_checks("evil.example.com/../x", "k", "k", "k")

    assert http["requests"] == []
    assert all(r.error for r in results)
