"""OrganizationUpdate.logo_url accepts only http(s) URLs."""

import pytest
from pydantic import ValidationError

from app.schemas.organization import OrganizationUpdate


def test_logo_url_https_accepted():
    body = OrganizationUpdate(logo_url="https://acme.test/logo.png")
    assert body.logo_url == "https://acme.test/logo.png"


def test_logo_url_javascript_rejected():
    with pytest.raises(ValidationError):
        OrganizationUpdate(logo_url="javascript:alert(1)")


def test_logo_url_data_rejected():
    with pytest.raises(ValidationError):
        OrganizationUpdate(logo_url="data:image/png;base64,iVBORw0KGgo=")


def test_logo_url_protocol_relative_rejected():
    with pytest.raises(ValidationError):
        OrganizationUpdate(logo_url="//evil.example/x.png")


def test_logo_url_empty_becomes_none():
    assert OrganizationUpdate(logo_url="").logo_url is None


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("HTTPS://a.test/x", "HTTPS://a.test/x"),
        ("  https://a.test/x  ", "https://a.test/x"),
        ("https://a.test/x\n", "https://a.test/x"),
        ("   ", None),
    ],
)
def test_logo_url_stripped_and_accepted(raw, stored):
    assert OrganizationUpdate(logo_url=raw).logo_url == stored


@pytest.mark.parametrize(
    "raw",
    [
        "http:///p",
        "https://",
        "http://a b",
        "https://a.test/x y",
        "https://a.test/\tx",
        "https://a.test/\x00",
    ],
)
def test_logo_url_malformed_rejected(raw):
    with pytest.raises(ValidationError):
        OrganizationUpdate(logo_url=raw)
