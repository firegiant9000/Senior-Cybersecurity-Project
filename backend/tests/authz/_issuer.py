"""Local Firebase ID-token issuer: an RSA key, a self-signed cert and a token minter."""

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

PROJECT_ID = "ht-authz-test"
KID = "authz-test-kid"
ISSUER = f"https://securetoken.google.com/{PROJECT_ID}"


@dataclass(frozen=True)
class SigningKey:
    private_key: rsa.RSAPrivateKey
    cert_pem: str

    @classmethod
    def generate(cls) -> "SigningKey":
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "authz-test")])
        now = datetime.now(UTC)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=1))
            .sign(private_key, hashes.SHA256())
        )
        return cls(
            private_key=private_key,
            cert_pem=cert.public_bytes(serialization.Encoding.PEM).decode(),
        )


def mint_id_token(
    key: SigningKey | None,
    *,
    uid: str,
    email: str,
    email_verified: bool = True,
    iat: int | None = None,
    exp: int | None = None,
    aud: str = PROJECT_ID,
    iss: str = ISSUER,
    kid: str = KID,
    alg: str = "RS256",
    hs_secret: str = "authz-hs-secret",  # noqa: S107 - test-only HS256 confusion secret
    extra: dict | None = None,
) -> str:
    """Mint a Firebase-shaped ID token. `alg` HS256/none build forged variants."""
    issued_at = int(time.time()) - 5 if iat is None else iat
    claims = {
        "iss": iss,
        "aud": aud,
        "sub": uid,
        "iat": issued_at,
        "exp": issued_at + 3600 if exp is None else exp,
        "auth_time": issued_at,
        "email": email,
        "email_verified": email_verified,
        "firebase": {"sign_in_provider": "password", "identities": {}},
    }
    if extra:
        claims.update(extra)
    headers = {"kid": kid}
    if alg == "none":
        return jwt.encode(claims, key=None, algorithm="none", headers=headers)
    if alg == "HS256":
        return jwt.encode(claims, hs_secret, algorithm="HS256", headers=headers)
    if key is None:
        raise ValueError("a SigningKey is required for asymmetric algorithms")
    return jwt.encode(claims, key.private_key, algorithm=alg, headers=headers)
