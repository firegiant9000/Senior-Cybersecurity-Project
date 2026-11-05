"""Shared rate-limiter instance used across all routers."""

import ipaddress

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings


def client_ip(request: Request) -> str:
    """Rate-limit key: the client address, optionally taken from the proxy header.

    Behind a reverse proxy the connecting peer is the proxy, so every caller
    would share one bucket. With ``RATE_LIMIT_TRUST_X_FORWARDED_FOR`` on, the key
    is the rightmost ``X-Forwarded-For`` entry: the address the nearest proxy saw
    and appended. Entries to its left are client-supplied and never used, so a
    spoofed header cannot pick the bucket. (Not uvicorn's
    ``--forwarded-allow-ips='*'``, which trusts the leftmost entry.) Turn it on
    only where every request reaches the app through a proxy that appends to or
    overwrites the header. An empty or malformed rightmost entry falls back to
    the peer.
    """
    if settings.RATE_LIMIT_TRUST_X_FORWARDED_FOR:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            candidate = forwarded.rsplit(",", 1)[-1].strip()
            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                pass
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)


def agent_token_key(request: Request) -> str:
    """Rate-limit key for agent uploads: the token prefix, not the source IP.

    Many hosts behind one NAT share an egress IP, so keying on the remote
    address would let one noisy agent throttle every other agent on the same
    network — and let an attacker rotate IPs to dodge the limit. The public
    ``ht_<prefix>_...`` prefix identifies the credential without exposing the
    secret. Falls back to the client address for malformed/missing headers so a
    junk request still can't bypass limiting entirely.
    """
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() == "bearer" and token.startswith("ht_"):
        parts = token.split("_", 2)
        if len(parts) == 3 and parts[1]:
            return f"agent:{parts[1]}"
    return client_ip(request)
