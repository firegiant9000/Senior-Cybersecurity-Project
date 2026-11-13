"""Size-capped streaming JSON fetch for feed ingestors (T-ING-06)."""

import asyncio
import json
from typing import Any

import httpx

FEED_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# FEED_TIMEOUT is per network read, so a peer trickling bytes never trips it. This is
# the overall wall-clock limit for one request including the body. 300 s leaves room
# for a 64 MiB NVD page (about 1.8 Mbit/s) while still freeing a stuck ingest worker.
FEED_DEADLINE_SECONDS = 300.0


class ResponseTooLargeError(Exception):
    """Raised when a feed response body exceeds the configured byte cap."""


class FeedDeadlineError(Exception):
    """Raised when a feed request exceeds its overall deadline."""


def _too_large(max_bytes: int) -> ResponseTooLargeError:
    # Deliberately omits the URL and body: the message may reach logs.
    return ResponseTooLargeError(f"response body exceeds {max_bytes} bytes")


async def get_json_capped(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
    deadline: float = FEED_DEADLINE_SECONDS,
    **kwargs: Any,
) -> Any:
    """GET ``url`` and parse JSON, refusing bodies larger than ``max_bytes``.

    The cap is applied to decoded bytes (gzip expansion counts) and reading
    stops as soon as it is exceeded. Content-Length is only an early check.
    The whole request, body included, must finish within ``deadline`` seconds.
    """
    try:
        async with asyncio.timeout(deadline), client.stream("GET", url, **kwargs) as resp:
            resp.raise_for_status()
            declared = resp.headers.get("content-length")
            if declared is not None:
                try:
                    if int(declared) > max_bytes:
                        raise _too_large(max_bytes)
                except ValueError:
                    pass  # malformed header; the streamed count is the real guard
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise _too_large(max_bytes)
                chunks.append(chunk)
    except TimeoutError:
        # Deliberately omits the URL: the message may reach logs.
        raise FeedDeadlineError(f"feed request exceeded {deadline:g}s deadline") from None
    return json.loads(b"".join(chunks))
