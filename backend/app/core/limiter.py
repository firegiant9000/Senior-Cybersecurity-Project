"""Shared rate-limiter instance used across all routers."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)


def agent_token_key(request: Request) -> str:
    """Rate-limit key for agent uploads: the token prefix, not the source IP.

    Many hosts behind one NAT share an egress IP, so keying on the remote
    address would let one noisy agent throttle every other agent on the same
    network — and let an attacker rotate IPs to dodge the limit. The public
    ``ht_<prefix>_...`` prefix identifies the credential without exposing the
    secret. Falls back to the remote address for malformed/missing headers so a
    junk request still can't bypass limiting entirely.
    """
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() == "bearer" and token.startswith("ht_"):
        parts = token.split("_", 2)
        if len(parts) == 3 and parts[1]:
            return f"agent:{parts[1]}"
    return get_remote_address(request)
