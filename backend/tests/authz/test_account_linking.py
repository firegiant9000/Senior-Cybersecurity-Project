"""T-AUTH-01/02/03: email-based account linking and the local account gates, with real tokens.

Every request here carries a token signed by the local issuer and verified by the real
Firebase Admin SDK code path; only the public-cert and account-lookup network edges are faked.
"""

from collections.abc import AsyncGenerator, Awaitable, Callable
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import delete, select

from app.db.engine import AsyncSessionLocal
from app.db.user import User
from tests.authz._issuer import mint_id_token
from tests.conftest import unique_email

ME = "/api/v1/auth/me"


@pytest_asyncio.fixture
async def local_user() -> AsyncGenerator[Callable[..., Awaitable[str]], None]:
    """Insert a local User row and remove it afterwards. Returns the row's email."""
    emails: list[str] = []

    async def make(*, firebase_uid: str | None = None, is_active: bool = True) -> str:
        email = unique_email()
        async with AsyncSessionLocal() as session:
            session.add(
                User(firebase_uid=firebase_uid, email=email, role="viewer", is_active=is_active)
            )
            await session.commit()
        emails.append(email)
        return email

    yield make
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.email.in_(emails)))
        await session.commit()


async def _bound_uid(email: str) -> str | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.firebase_uid).where(User.email == email))
        return result.scalar_one()


def _fresh_uid() -> str:
    return f"authz-{uuid4().hex[:12]}"


async def test_unverified_email_does_not_link_existing_account(
    authz_client, accounts, signing_key, local_user
):
    email = await local_user()
    uid = _fresh_uid()
    accounts.add(uid, email, email_verified=False)
    token = mint_id_token(signing_key, uid=uid, email=email, email_verified=False)
    response = await (await authz_client(token)).get(ME)
    assert response.status_code == 403
    assert await _bound_uid(email) is None


async def test_verified_email_links_existing_unbound_account(
    authz_client, accounts, signing_key, local_user
):
    """Control for the unverified case: same setup, verified email."""
    email = await local_user()
    uid = _fresh_uid()
    accounts.add(uid, email)
    token = mint_id_token(signing_key, uid=uid, email=email, email_verified=True)
    response = await (await authz_client(token)).get(ME)
    assert response.status_code == 200
    assert response.json()["email"] == email
    assert await _bound_uid(email) == uid


async def test_account_bound_to_another_uid_is_not_relinked(
    authz_client, accounts, signing_key, local_user
):
    original_uid = _fresh_uid()
    email = await local_user(firebase_uid=original_uid)
    intruder_uid = _fresh_uid()
    accounts.add(intruder_uid, email)
    token = mint_id_token(signing_key, uid=intruder_uid, email=email, email_verified=True)
    response = await (await authz_client(token)).get(ME)
    assert response.status_code == 403
    assert await _bound_uid(email) == original_uid


async def test_token_without_email_claim_rejected(authz_client, accounts, signing_key, local_user):
    email = await local_user()
    uid = _fresh_uid()
    accounts.add(uid, email)
    token = mint_id_token(signing_key, uid=uid, email=email, drop_claims=("email",))
    response = await (await authz_client(token)).get(ME)
    assert response.status_code == 401
    assert await _bound_uid(email) is None


async def test_inactive_local_user_rejected(authz_client, accounts, signing_key, local_user):
    uid = _fresh_uid()
    email = await local_user(firebase_uid=uid, is_active=False)
    accounts.add(uid, email)
    token = mint_id_token(signing_key, uid=uid, email=email)
    response = await (await authz_client(token)).get(ME)
    assert response.status_code == 403
