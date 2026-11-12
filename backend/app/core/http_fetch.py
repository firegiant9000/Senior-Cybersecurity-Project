"""Size-capped streaming JSON fetch for feed ingestors (T-ING-06)."""

import json
from typing import Any

import httpx

FEED_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ResponseTooLargeError(Exception):
    """Raised when a feed response body exceeds the configured byte cap."""


def _too_large(max_bytes: int) -> ResponseTooLargeError:
    # Deliberately omits the URL and body: the message may reach logs.
    return ResponseTooLargeError(f"response body exceeds {max_bytes} bytes")


async def get_json_capped(
    client: httpx.AsyncClient, url: str, *, max_bytes: int, **kwargs: Any
) -> Any:
    """GET ``url`` and parse JSON, refusing bodies larger than ``max_bytes``.

    The cap is applied to decoded bytes (gzip expansion counts) and reading
    stops as soon as it is exceeded. Content-Length is only an early check.
    """
    async with client.stream("GET", url, **kwargs) as resp:
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
    return json.loads(b"".join(chunks))
