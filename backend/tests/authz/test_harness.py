"""Harness guard: Firebase verification in this folder is real, not mocked."""

import unittest.mock

import firebase_admin.auth

from tests.authz._fakes import IdentityToolkitAdapter
from tests.authz._issuer import mint_id_token


def test_verify_id_token_is_real():
    verify = firebase_admin.auth.verify_id_token
    assert not isinstance(verify, unittest.mock.NonCallableMock)
    assert verify.__module__ == "firebase_admin.auth"


async def test_valid_token_accepted(authz_client, new_user, signing_key):
    uid, email = new_user()
    token = mint_id_token(signing_key, uid=uid, email=email)
    client = await authz_client(token)
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == email


async def test_cert_fake_was_hit(
    authz_client, new_user, signing_key, cert_adapter, firebase_test_app
):
    toolkit: IdentityToolkitAdapter = firebase_test_app[1]
    uid, email = new_user()
    token = mint_id_token(signing_key, uid=uid, email=email)
    client = await authz_client(token)
    cert_before = cert_adapter.hits
    toolkit_before = toolkit.hits
    for _ in range(2):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
    assert cert_adapter.hits >= cert_before + 2
    assert toolkit.hits > toolkit_before
