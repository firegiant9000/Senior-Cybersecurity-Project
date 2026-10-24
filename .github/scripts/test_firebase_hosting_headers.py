import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]


def spa_headers() -> dict[str, str]:
    """The "**" entry's headers from firebase.json, with names lower-cased."""
    config = json.loads((ROOT / "firebase.json").read_text(encoding="utf-8"))
    for entry in config["hosting"].get("headers", []):
        if entry["source"] == "**":
            return {h["key"].lower(): h["value"] for h in entry["headers"]}
    return {}


def csp_directives(csp: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for part in csp.split(";"):
        tokens = part.split()
        if tokens:
            directives[tokens[0]] = tokens[1:]
    return directives


def production_api_origin() -> str:
    for line in (ROOT / "frontend" / ".env.production").read_text(encoding="utf-8").splitlines():
        if line.startswith("VITE_API_BASE_URL="):
            url = urlparse(line.split("=", 1)[1].strip())
            return f"{url.scheme}://{url.netloc}"
    raise AssertionError("VITE_API_BASE_URL missing from frontend/.env.production")


class FirebaseHostingHeadersTests(unittest.TestCase):
    def csp(self) -> dict[str, list[str]]:
        value = spa_headers().get("content-security-policy")
        self.assertIsNotNone(value, "SPA has no Content-Security-Policy")
        return csp_directives(value)

    def test_spa_sends_security_headers(self):
        headers = spa_headers()
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(headers.get("x-frame-options"), "DENY")
        self.assertEqual(headers.get("referrer-policy"), "strict-origin-when-cross-origin")
        self.assertIn("content-security-policy", headers)

    def test_spa_csp_blocks_framing_and_inline_script(self):
        csp = self.csp()
        self.assertEqual(csp.get("frame-ancestors"), ["'none'"])
        self.assertEqual(csp.get("object-src"), ["'none'"])
        self.assertEqual(csp.get("script-src"), ["'self'"])
        self.assertEqual(csp.get("base-uri"), ["'self'"])
        for name, sources in csp.items():
            self.assertNotIn("'unsafe-eval'", sources, name)
            self.assertNotIn("*", sources, name)
        self.assertNotIn("'unsafe-inline'", csp.get("script-src", []))

    def test_spa_csp_allows_firebase_auth_endpoints(self):
        connect = self.csp().get("connect-src", [])
        self.assertIn("https://identitytoolkit.googleapis.com", connect)
        self.assertIn("https://securetoken.googleapis.com", connect)

    def test_spa_csp_allows_the_production_api(self):
        # Pins the committed .env.production value only; CI builds with
        # VITE_API_BASE_URL from secrets, which is an owner checkbox in the PR.
        self.assertIn(production_api_origin(), self.csp().get("connect-src", []))

    def test_spa_csp_allows_fonts_and_org_logo_images(self):
        csp = self.csp()
        self.assertIn("https://fonts.googleapis.com", csp.get("style-src", []))
        self.assertIn("https://fonts.gstatic.com", csp.get("font-src", []))
        self.assertIn("https:", csp.get("img-src", []))


if __name__ == "__main__":
    unittest.main()
