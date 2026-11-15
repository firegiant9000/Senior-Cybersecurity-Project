"""Public, DNS-only domain check (#295).

Looks up SPF and DMARC only (no HTTP, no TLS, no DKIM) and rates the domain's
spoofability. A failed lookup is reported as ``unavailable`` and is never a
rating. The host is never logged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import dns.asyncresolver
import dns.exception
import dns.resolver
from cachetools import TTLCache

from app.services.domain_checks import (
    _DNS_TIMEOUT,
    dmarc_policy_from_record,
)

Status = Literal["ok", "domain_not_found", "unavailable"]
DmarcPolicy = Literal["none", "quarantine", "reject"]
Rating = Literal["protected", "monitoring_only", "spoofable"]

_POLICIES: tuple[str, ...] = ("none", "quarantine", "reject")


@dataclass(frozen=True)
class PublicDomainCheck:
    status: Status
    spf_found: bool | None = None  # None unless status == "ok"
    dmarc_found: bool | None = None
    dmarc_policy: DmarcPolicy | None = None
    rating: Rating | None = None  # None unless status == "ok"
    multiple_dmarc: bool = False  # internal: picks the explanation, not in the HTTP response


SPECIAL_USE_TLDS: frozenset[str] = frozenset(
    {
        "internal",
        "local",
        "localhost",
        "localdomain",
        "lan",
        "home",
        "corp",
        "arpa",
        "test",
        "invalid",
        "example",
        "onion",
        "alt",
    }
)


def is_public_checkable(host: str) -> bool:
    """False for names under special-use / private TLDs (never probe the resolver's namespace)."""
    return host.rsplit(".", 1)[-1] not in SPECIAL_USE_TLDS


_DMARC_VERSION = re.compile(r"^v\s*=\s*DMARC1\s*(;|$)")


EXPLANATIONS: dict[str, str] = {
    "protected": (
        "Your domain tells receiving mail servers to block or quarantine email "
        "that pretends to come from you."
    ),
    "monitoring_only": (
        "Your domain has a DMARC record, but it only asks for reports, so email "
        "pretending to be you can still be delivered."
    ),
    "spoofable": (
        "Your domain has no DMARC record, so nothing tells mail servers to stop "
        "email that pretends to come from you."
    ),
    "multiple_dmarc": (
        "Your domain publishes more than one DMARC record, so mail servers ignore them "
        "and nothing stops email that pretends to come from you."
    ),
    "domain_not_found": "We couldn't find that domain. Check the spelling and try again.",
    "unavailable": ("We couldn't finish the check just now. Please try again in a few minutes."),
}

CACHE_TTL_SECONDS = 900
CACHE_MAX_ENTRIES = 1024
_cache: TTLCache[str, PublicDomainCheck] = TTLCache(
    maxsize=CACHE_MAX_ENTRIES, ttl=CACHE_TTL_SECONDS
)

_UNAVAILABLE = PublicDomainCheck(status="unavailable")
_NOT_FOUND = PublicDomainCheck(status="domain_not_found")


def _make_resolver() -> dns.asyncresolver.Resolver:
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = _DNS_TIMEOUT
    resolver.lifetime = _DNS_TIMEOUT
    return resolver


def rate(dmarc_found: bool, dmarc_policy: DmarcPolicy | None) -> Rating:  # noqa: FBT001
    """SPF does not affect the rating; only DMARC presence and enforcement do."""
    if not dmarc_found:
        return "spoofable"
    if dmarc_policy in ("quarantine", "reject"):
        return "protected"
    return "monitoring_only"


def _text(rdata) -> str:  # noqa: ANN001 - dnspython rdata, untyped
    """TXT text; undecodable bytes become U+FFFD so the record still counts (RFC 7489)."""
    return "".join(s.decode(errors="replace") if isinstance(s, bytes) else s for s in rdata.strings)


def _is_spf(text: str) -> bool:
    lowered = text.lower()
    return lowered == "v=spf1" or lowered.startswith("v=spf1 ")


async def _dmarc_records(resolver: dns.asyncresolver.Resolver, host: str) -> list[str] | None:
    """DMARC-looking TXT records at _dmarc.<host>; None when the lookup failed."""
    try:
        answers = await resolver.resolve(f"_dmarc.{host}", "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.DNSException:
        return None
    texts = (_text(r).strip() for r in answers)
    return [t for t in texts if _DMARC_VERSION.match(t)]


def _policy_of(record: str) -> DmarcPolicy | None:
    """The record's policy; None when it has several p= tags or an unknown value."""
    tags = [p for p in (part.strip() for part in record.split(";")) if p.lower().startswith("p=")]
    if len(tags) != 1:
        return None
    candidate = dmarc_policy_from_record(record)
    return candidate if candidate in _POLICIES else None  # type: ignore[return-value]


async def check_public_domain(host: str) -> PublicDomainCheck:
    """Check SPF/DMARC for an already-normalized hostname."""
    cached = _cache.get(host)
    if cached is not None:
        return cached

    resolver = _make_resolver()

    # SPF: TXT on the apex. NXDOMAIN means the domain does not exist.
    try:
        answers = await resolver.resolve(host, "TXT")
    except dns.resolver.NXDOMAIN:
        _cache[host] = _NOT_FOUND
        return _NOT_FOUND
    except dns.resolver.NoAnswer:
        spf_found = False
    except dns.exception.DNSException:
        return _UNAVAILABLE
    else:
        spf_found = any(_is_spf(_text(r)) for r in answers)

    dmarc_records = await _dmarc_records(resolver, host)
    if dmarc_records is None:
        return _UNAVAILABLE

    dmarc_found = len(dmarc_records) == 1
    policy = _policy_of(dmarc_records[0]) if dmarc_found else None

    result = PublicDomainCheck(
        status="ok",
        spf_found=spf_found,
        dmarc_found=dmarc_found,
        dmarc_policy=policy,
        rating=rate(dmarc_found, policy),
        multiple_dmarc=len(dmarc_records) > 1,
    )
    _cache[host] = result
    return result
