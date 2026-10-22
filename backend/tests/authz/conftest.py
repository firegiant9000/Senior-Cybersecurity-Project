"""Fixtures for the authz suite: real Firebase token verification, faked network edge.

The parent conftest autouse-mocks `firebase_admin.auth.verify_id_token`; this folder
overrides that fixture (same name) with a no-op so verification runs for real against a
locally signed key.
"""

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from uuid import uuid4

import firebase_admin
import google.auth.credentials
import pytest
import pytest_asyncio
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from httpx import ASGITransport, AsyncClient

from app.core.limiter import limiter
from app.main import app
from tests.authz._fakes import (
    CERT_URL,
    IDENTITY_TOOLKIT_PREFIX,
    CertAdapter,
    FakeAccounts,
    IdentityToolkitAdapter,
)
from tests.authz._issuer import KID, PROJECT_ID, SigningKey
from tests.conftest import unique_email


class _StaticGoogleCredentials(google.auth.credentials.Credentials):
    def __init__(self):
        super().__init__()
        self.token = "authz-test-access-token"  # noqa: S105
        self.expiry = None

    def refresh(self, request):
        pass


class _StaticCredential(credentials.Base):
    def get_credential(self):
        return _StaticGoogleCredentials()


@pytest.fixture(autouse=True)
def _mock_firebase_verify():
    """Override the global mock: token verification is real in this folder."""
    yield


@pytest.fixture(scope="package")
def signing_key() -> SigningKey:
    return SigningKey.generate()


@pytest.fixture(scope="package", autouse=True)
def firebase_test_app(
    signing_key: SigningKey,
) -> Generator[tuple[CertAdapter, IdentityToolkitAdapter, FakeAccounts], None, None]:
    assert not firebase_admin._apps, "a Firebase app already exists; authz needs a clean slate"
    fb_app = firebase_admin.initialize_app(
        credential=_StaticCredential(), options={"projectId": PROJECT_ID}
    )
    cert_adapter = CertAdapter({KID: signing_key.cert_pem})
    accounts = FakeAccounts()
    toolkit_adapter = IdentityToolkitAdapter(accounts)
    client = firebase_auth._get_client(fb_app)
    client._token_verifier.request.session.mount(CERT_URL, cert_adapter)
    client._user_manager.http_client.session.mount(IDENTITY_TOOLKIT_PREFIX, toolkit_adapter)
    try:
        yield cert_adapter, toolkit_adapter, accounts
    finally:
        firebase_admin.delete_app(fb_app)
        assert firebase_admin._apps == {}


@pytest.fixture
def cert_adapter(firebase_test_app) -> CertAdapter:
    return firebase_test_app[0]


@pytest.fixture
def accounts(firebase_test_app) -> FakeAccounts:
    registry = firebase_test_app[2]
    registry.clear()
    return registry


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()


@pytest_asyncio.fixture
async def authz_client() -> AsyncGenerator[Callable[[str | None], Awaitable[AsyncClient]], None]:
    """Factory for clients that send a real (or no) bearer token."""
    opened: list[AsyncClient] = []

    async def make(token: str | None) -> AsyncClient:
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=headers
        )
        opened.append(client)
        return client

    yield make
    for client in opened:
        await client.aclose()


@pytest.fixture
def new_user(accounts: FakeAccounts, signing_key: SigningKey) -> Callable[..., tuple[str, str]]:  # noqa: ARG001
    def make() -> tuple[str, str]:
        uid = f"authz-{uuid4().hex[:12]}"
        email = unique_email()
        accounts.add(uid, email)
        return uid, email

    return make
