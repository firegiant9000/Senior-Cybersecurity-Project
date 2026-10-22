"""T-AUTH-07: forged, expired, revoked and otherwise invalid ID tokens are rejected (401)."""

import secrets
import time

from sqlalchemy import select

from app.db.engine import AsyncSessionLocal
from app.db.user import User
from tests.authz._issuer import KID, SigningKey, mint_id_token

ME = "/api/v1/auth/me"
AGENT_SCAN_CREATE = "/api/v1/inventory/scans"
AGENT_SCAN_READ = "/api/v1/inventory/scans/1"


async def _user_exists(uid: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.id).where(User.firebase_uid == uid))
        return result.first() is not None


async def _assert_rejected(authz_client, token: str, uid: str) -> None:
    client = await authz_client(token)
    response = await client.get(ME)
    assert response.status_code == 401
    assert not await _user_exists(uid), "a rejected token must not auto-create an account"


async def test_forged_signature_rejected(authz_client, new_user):
    uid, email = new_user()
    forger = SigningKey.generate()
    token = mint_id_token(forger, uid=uid, email=email, kid=KID)
    await _assert_rejected(authz_client, token, uid)


async def test_expired_token_rejected(authz_client, new_user, signing_key):
    uid, email = new_user()
    now = int(time.time())
    token = mint_id_token(signing_key, uid=uid, email=email, iat=now - 3630, exp=now - 30)
    await _assert_rejected(authz_client, token, uid)


async def test_wrong_audience_rejected(authz_client, new_user, signing_key):
    uid, email = new_user()
    token = mint_id_token(signing_key, uid=uid, email=email, aud="other-project")
    await _assert_rejected(authz_client, token, uid)


async def test_wrong_issuer_rejected(authz_client, new_user, signing_key):
    uid, email = new_user()
    token = mint_id_token(
        signing_key, uid=uid, email=email, iss="https://securetoken.google.com/other-project"
    )
    await _assert_rejected(authz_client, token, uid)


async def test_hs256_token_rejected(authz_client, new_user):
    uid, email = new_user()
    token = mint_id_token(None, uid=uid, email=email, alg="HS256", hs_secret="x" * 32)
    await _assert_rejected(authz_client, token, uid)


async def test_alg_none_token_rejected(authz_client, new_user):
    uid, email = new_user()
    token = mint_id_token(None, uid=uid, email=email, alg="none")
    await _assert_rejected(authz_client, token, uid)


async def test_revoked_token_rejected(authz_client, new_user, signing_key, accounts):
    uid, email = new_user()
    now = int(time.time())
    accounts.revoke(uid, at=now - 10)
    token = mint_id_token(signing_key, uid=uid, email=email, iat=now - 60)
    await _assert_rejected(authz_client, token, uid)


async def test_token_after_revocation_accepted(authz_client, new_user, signing_key, accounts):
    """Control for the revoked-token test: same setup, token issued after the revocation."""
    uid, email = new_user()
    now = int(time.time())
    accounts.revoke(uid, at=now - 120)
    token = mint_id_token(signing_key, uid=uid, email=email, iat=now - 5)
    client = await authz_client(token)
    response = await client.get(ME)
    assert response.status_code == 200


async def test_disabled_user_rejected(authz_client, new_user, signing_key, accounts):
    uid, email = new_user()
    accounts.disable(uid)
    token = mint_id_token(signing_key, uid=uid, email=email)
    await _assert_rejected(authz_client, token, uid)


async def test_unknown_firebase_account_rejected(authz_client, new_user, signing_key, accounts):
    uid, email = new_user()
    accounts.clear()
    token = mint_id_token(signing_key, uid=uid, email=email)
    await _assert_rejected(authz_client, token, uid)


async def test_missing_authorization_rejected(authz_client):
    client = await authz_client(None)
    response = await client.get(ME)
    assert response.status_code == 401


async def test_malformed_bearer_rejected(authz_client):
    client = await authz_client("not-a-jwt")
    response = await client.get(ME)
    assert response.status_code == 401


async def test_agent_token_on_human_route_rejected(authz_client):
    client = await authz_client("ht_abcd1234_" + secrets.token_urlsafe(32))
    response = await client.get(ME)
    assert response.status_code == 401


async def test_firebase_token_on_agent_routes_rejected(authz_client, new_user, signing_key):
    uid, email = new_user()
    token = mint_id_token(signing_key, uid=uid, email=email)
    client = await authz_client(token)
    created = await client.post(AGENT_SCAN_CREATE, json={})
    read = await client.get(AGENT_SCAN_READ)
    assert created.status_code == 401
    assert read.status_code == 401
    assert not await _user_exists(uid), "a rejected token must not auto-create an account"
