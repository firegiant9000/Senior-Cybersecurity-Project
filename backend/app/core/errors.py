"""Helpers for keeping raw exception text out of stored and returned error fields."""

from __future__ import annotations

import re

_CLASS_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def public_error(stored: str | None) -> str | None:
    """Return a stored error that is safe to show: a bare class name, else ``"error"``.

    Rows written before errors were reduced to a class name may hold raw SDK text
    (URLs, keys), so anything that is not a plain identifier is replaced.
    """
    if not stored:
        return None
    return stored if _CLASS_NAME.fullmatch(stored) else "error"
