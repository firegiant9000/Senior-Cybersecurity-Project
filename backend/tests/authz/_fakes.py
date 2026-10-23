"""Network-edge fakes for the Firebase Admin SDK's `requests` sessions."""

import json

import requests
from requests.adapters import BaseAdapter

from tests.authz._issuer import PROJECT_ID

CERT_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
)
IDENTITY_TOOLKIT_PREFIX = "https://identitytoolkit.googleapis.com/"
_LOOKUP_URL = f"https://identitytoolkit.googleapis.com/v1/projects/{PROJECT_ID}/accounts:lookup"


def _response(
    request: requests.PreparedRequest, status: int, body: object, headers: dict | None = None
) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode()
    response.headers.update({"Content-Type": "application/json", **(headers or {})})
    response.url = request.url
    response.request = request
    response.encoding = "utf-8"
    return response


class CertAdapter(BaseAdapter):
    """Serves our local signing cert as the Google public-cert endpoint."""

    def __init__(self, cert_pem_by_kid: dict[str, str]):
        super().__init__()
        self.cert_pem_by_kid = cert_pem_by_kid
        self.hits = 0

    def send(self, request, **kwargs):  # noqa: ARG002
        self.hits += 1
        return _response(request, 200, self.cert_pem_by_kid, {"Cache-Control": "no-store"})

    def close(self):
        pass


class FakeAccounts:
    """In-memory Firebase user registry backing the Identity Toolkit fake."""

    def __init__(self):
        self._users: dict[str, dict] = {}

    def add(self, uid: str, email: str, *, email_verified: bool = True) -> None:
        self._users[uid] = {
            "localId": uid,
            "email": email,
            "emailVerified": email_verified,
            "disabled": False,
            "validSince": "0",
        }

    def disable(self, uid: str) -> None:
        self._users[uid]["disabled"] = True

    def revoke(self, uid: str, *, at: int) -> None:
        self._users[uid]["validSince"] = str(at)

    def lookup(self, uid: str) -> dict | None:
        return self._users.get(uid)

    def clear(self) -> None:
        self._users.clear()


class IdentityToolkitAdapter(BaseAdapter):
    """Answers accounts:lookup from FakeAccounts; any other call is a visible 404."""

    def __init__(self, accounts: FakeAccounts):
        super().__init__()
        self.accounts = accounts
        self.hits = 0

    def send(self, request, **kwargs):  # noqa: ARG002
        self.hits += 1
        if request.method != "POST" or request.url != _LOOKUP_URL:
            error = {
                "error": {
                    "code": 404,
                    "message": f"unexpected call {request.method} {request.url}",
                }
            }
            return _response(request, 404, error)
        body = request.body
        if isinstance(body, bytes):
            body = body.decode()
        uids = json.loads(body).get("localId", [])
        users = [record for uid in uids if (record := self.accounts.lookup(uid)) is not None]
        return _response(request, 200, {"users": users} if users else {})

    def close(self):
        pass
