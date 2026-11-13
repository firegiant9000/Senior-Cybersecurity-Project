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
