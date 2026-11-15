"""Public, DNS-only domain check (#295).

Looks up SPF and DMARC only (no HTTP, no TLS, no DKIM) and rates the domain's
spoofability. A failed lookup is reported as ``unavailable`` and is never a
rating. The host is never logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import dns.asyncresolver
import dns.exception
import dns.resolver
from cachetools import TTLCache

from app.services.domain_checks import (
    _DNS_TIMEOUT,
    dmarc_policy_from_record,
    txt_record_text,
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
    """TXT text, or "" for a record that is not valid UTF-8 (visitor-controlled data)."""
    try:
        return txt_record_text(rdata)
    except UnicodeDecodeError:
        return ""


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
    return [t for t in texts if t.startswith("v=DMARC1")]


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
    policy: DmarcPolicy | None = None
    if dmarc_found:
        candidate = dmarc_policy_from_record(dmarc_records[0])
        if candidate in _POLICIES:
            policy = candidate  # type: ignore[assignment]

    result = PublicDomainCheck(
        status="ok",
        spf_found=spf_found,
        dmarc_found=dmarc_found,
        dmarc_policy=policy,
        rating=rate(dmarc_found, policy),
    )
    _cache[host] = result
    return result
