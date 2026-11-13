"""Unit tests for app.core.errors.public_error."""

import pytest

from app.core.errors import public_error


def test_bare_class_name_is_kept():
    assert public_error("RuntimeError") == "RuntimeError"
    assert public_error("_Private1") == "_Private1"


@pytest.mark.parametrize(
    "stored",
    [
        "ValueError: key=abc",
        "has space",
        "pkg.module.Error",
        "boom\nsecond line",
        "1StartsWithDigit",
    ],
)
def test_anything_else_becomes_generic_error(stored):
    assert public_error(stored) == "error"


@pytest.mark.parametrize("stored", [None, ""])
def test_empty_or_none_is_none(stored):
    assert public_error(stored) is None
