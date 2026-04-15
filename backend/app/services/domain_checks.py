"""Domain reconnaissance checks used by the Findings Engine.

Tier 1 (no API key required):
  - DNS: SPF, DMARC, DKIM presence
  - HTTP: security response headers
  - SSL/TLS: certificate expiry, protocol version, self-signed detection
  - Tech fingerprinting: detect technologies from HTTP response

Tier 2 (free, no API key required):
  - crt.sh Certificate Transparency log search (subdomain enumeration)

Tier 2 (requires API key):
  - Have I Been Pwned domain breach search (HIBP_API_KEY)
  - Shodan host lookup (SHODAN_API_KEY)
  - AlienVault OTX threat intel (OTX_API_KEY)
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 5.0  # seconds
_DNS_TIMEOUT = 5.0

# Shodan cache: keyed by IP, 24-hour TTL, max 500 entries
_shodan_cache: TTLCache = TTLCache(maxsize=500, ttl=86400)

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DnsCheckResult:
    domain: str
    spf_found: bool = False
    spf_record: str | None = None
    dmarc_found: bool = False
    dmarc_policy: str | None = None  # "none" | "quarantine" | "reject"
    dmarc_record: str | None = None
    dkim_selector_found: bool = False  # checks common selectors
    error: str | None = None


@dataclass
class HttpHeaderResult:
    domain: str
    reachable: bool = False
    has_hsts: bool = False
    has_csp: bool = False
    has_x_frame_options: bool = False
    has_x_content_type: bool = False
    has_permissions_policy: bool = False
    status_code: int | None = None
    error: str | None = None


@dataclass
class SslCheckResult:
    domain: str
    reachable: bool = False
    issuer: str | None = None
    expiry: datetime | None = None
    days_until_expiry: int | None = None
    self_signed: bool = False
    tls_version: str | None = None
    error: str | None = None


@dataclass
class CrtShResult:
    domain: str
    subdomains: list[str] = field(default_factory=list)
    cert_count: int = 0
    error: str | None = None


@dataclass
class HibpResult:
    domain: str
    breaches_found: int = 0
    breach_names: list[str] = field(default_factory=list)
    error: str | None = None
    skipped: bool = False  # True when HIBP_API_KEY is not configured


@dataclass
class TechFingerprintResult:
    domain: str
    detected: list[dict] = field(default_factory=list)  # [{name, categories, version?}]
    error: str | None = None


@dataclass
class ShodanHostResult:
    domain: str
    ip: str | None = None
    open_ports: list[int] = field(default_factory=list)
    vulns: list[str] = field(default_factory=list)  # CVE IDs
    services: list[dict] = field(default_factory=list)  # [{port, product, version?}]
    isp: str | None = None
    error: str | None = None
    skipped: bool = False  # True when SHODAN_API_KEY is not configured


@dataclass
class OtxResult:
    domain: str
    pulse_count: int = 0
    malware_families: list[str] = field(default_factory=list)
    reputation_score: int | None = None
    error: str | None = None
    skipped: bool = False  # True when OTX_API_KEY is not configured


# ---------------------------------------------------------------------------
# Tier 1: DNS checks (SPF / DMARC / DKIM)
# ---------------------------------------------------------------------------

_COMMON_DKIM_SELECTORS = ["default", "google", "mail", "selector1", "selector2", "k1", "dkim"]


async def check_dns(domain: str) -> DnsCheckResult:
    """Query DNS TXT records for SPF, DMARC, and common DKIM selectors."""
    result = DnsCheckResult(domain=domain)
    try:
        import dns.asyncresolver  # type: ignore[import-untyped]
        import dns.exception  # type: ignore[import-untyped]

        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = _DNS_TIMEOUT
        resolver.lifetime = _DNS_TIMEOUT

        # SPF — TXT records on the apex domain
        try:
            answers = await resolver.resolve(domain, "TXT")
            for rdata in answers:
                txt = "".join(s.decode() if isinstance(s, bytes) else s for s in rdata.strings)
                if txt.startswith("v=spf1"):
                    result.spf_found = True
                    result.spf_record = txt
                    break
        except (dns.exception.DNSException, Exception):
            pass

        # DMARC — TXT record at _dmarc.<domain>
        try:
            answers = await resolver.resolve(f"_dmarc.{domain}", "TXT")
            for rdata in answers:
                txt = "".join(s.decode() if isinstance(s, bytes) else s for s in rdata.strings)
                if txt.startswith("v=DMARC1"):
                    result.dmarc_found = True
                    result.dmarc_record = txt
                    # Extract p= policy
                    for part in txt.split(";"):
                        part = part.strip()
                        if part.lower().startswith("p="):
                            result.dmarc_policy = part.split("=", 1)[1].strip().lower()
                    break
        except (dns.exception.DNSException, Exception):
            pass

        # DKIM — check common selectors
        for selector in _COMMON_DKIM_SELECTORS:
            try:
                await resolver.resolve(f"{selector}._domainkey.{domain}", "TXT")
                result.dkim_selector_found = True
                break
            except (dns.exception.DNSException, Exception):
                continue

    except ImportError:
        result.error = "dnspython not installed"
    except Exception as exc:
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# Tier 1: HTTP security headers
# ---------------------------------------------------------------------------

_SECURITY_HEADERS = {
    "strict-transport-security": "has_hsts",
    "content-security-policy": "has_csp",
    "x-frame-options": "has_x_frame_options",
    "x-content-type-options": "has_x_content_type",
    "permissions-policy": "has_permissions_policy",
}


async def check_http_headers(domain: str) -> HttpHeaderResult:
    """Fetch the org's primary domain and inspect security response headers."""
    result = HttpHeaderResult(domain=domain)

    # Try HTTPS first, fall back to HTTP
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            async with httpx.AsyncClient(
                timeout=_HTTP_TIMEOUT,
                follow_redirects=True,
                verify=False,  # noqa: S501 — intentionally skip cert for header check
            ) as client:
                resp = await client.get(url)

            result.reachable = True
            result.status_code = resp.status_code

            headers_lower = {k.lower(): v for k, v in resp.headers.items()}
            for header_name, attr in _SECURITY_HEADERS.items():
                if header_name in headers_lower:
                    setattr(result, attr, True)

            return result
        except httpx.RequestError:
            continue
        except Exception as exc:
            # Log but continue to HTTP fallback instead of returning early
            logger.debug("Non-request error on %s://%s: %s", scheme, domain, exc)
            continue

    result.error = "Domain not reachable over HTTP or HTTPS"
    return result


# ---------------------------------------------------------------------------
# Tier 1: SSL/TLS certificate check
# ---------------------------------------------------------------------------


async def check_ssl(domain: str) -> SslCheckResult:
    """Check the SSL/TLS certificate for the org's primary domain."""
    result = SslCheckResult(domain=domain)

    def _sync_check() -> SslCheckResult:
        ctx = ssl.create_default_context()
        try:
            with socket.create_connection((domain, 443), timeout=_HTTP_TIMEOUT) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    result.reachable = True
                    result.tls_version = ssock.version()

                    cert = ssock.getpeercert()
                    if cert:
                        # Expiry
                        not_after = cert.get("notAfter")
                        if not_after:
                            expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                                tzinfo=timezone.utc
                            )
                            result.expiry = expiry_dt
                            result.days_until_expiry = (
                                expiry_dt - datetime.now(UTC)
                            ).days

                        # Issuer — check for self-signed (issuer == subject)
                        subject = dict(x[0] for x in cert.get("subject", []))
                        issuer = dict(x[0] for x in cert.get("issuer", []))
                        result.issuer = issuer.get("organizationName") or issuer.get(
                            "commonName"
                        )
                        result.self_signed = subject == issuer
        except ssl.SSLCertVerificationError:
            # Connect again without verification to inspect the cert anyway
            noverify_ctx = ssl.create_default_context()
            noverify_ctx.check_hostname = False
            noverify_ctx.verify_mode = ssl.CERT_NONE
            try:
                with socket.create_connection((domain, 443), timeout=_HTTP_TIMEOUT) as sock:
                    with noverify_ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                        result.reachable = True
                        result.tls_version = ssock.version()
                        result.self_signed = True
            except Exception as inner:
                result.error = str(inner)
        except (OSError, socket.timeout) as exc:
            result.error = str(exc)
        except Exception as exc:
            result.error = str(exc)
        return result

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_check)


# ---------------------------------------------------------------------------
# Tier 1: Technology fingerprinting (Wappalyzer-style)
# ---------------------------------------------------------------------------

# Curated technology signatures.  Each entry:
#   name, categories, header_patterns, meta_patterns, body_patterns
# Patterns are compiled once at import time for performance.

_TECH_SIGNATURES: list[dict] = []


def _sig(
    name: str,
    categories: list[str],
    *,
    headers: dict[str, str] | None = None,
    meta: dict[str, str] | None = None,
    body: list[str] | None = None,
    cookies: list[str] | None = None,
) -> None:
    _TECH_SIGNATURES.append({
        "name": name,
        "categories": categories,
        "headers": {k.lower(): re.compile(v, re.I) for k, v in (headers or {}).items()},
        "meta": {k.lower(): re.compile(v, re.I) for k, v in (meta or {}).items()},
        "body": [re.compile(p, re.I) for p in (body or [])],
        "cookies": [c.lower() for c in (cookies or [])],
    })


# --- Web servers ---
_sig("Apache", ["Web Server"], headers={"server": r"Apache"})
_sig("Nginx", ["Web Server"], headers={"server": r"nginx"})
_sig("Microsoft IIS", ["Web Server"], headers={"server": r"Microsoft-IIS"})
_sig("LiteSpeed", ["Web Server"], headers={"server": r"LiteSpeed"})
_sig("Caddy", ["Web Server"], headers={"server": r"Caddy"})

# --- Language / Runtime ---
_sig("PHP", ["Programming Language"], headers={"x-powered-by": r"PHP"}, cookies=["PHPSESSID"])
_sig("ASP.NET", ["Web Framework"], headers={"x-powered-by": r"ASP\.NET"}, cookies=["ASP.NET_SessionId"])
_sig("Express", ["Web Framework"], headers={"x-powered-by": r"Express"})
_sig("Node.js", ["Runtime"], headers={"x-powered-by": r"(?:Express|Node)"})
_sig("Python", ["Programming Language"], headers={"server": r"(?:gunicorn|uvicorn|waitress|daphne)"})
_sig("Java", ["Programming Language"], headers={"x-powered-by": r"(?:Servlet|JSP|JSF)"}, cookies=["JSESSIONID"])

# --- CMS ---
_sig("WordPress", ["CMS"], meta={"generator": r"WordPress"}, body=[r"/wp-content/", r"/wp-includes/"])
_sig("Drupal", ["CMS"], meta={"generator": r"Drupal"}, headers={"x-drupal-cache": r"."}, body=[r"/sites/default/files/"])
_sig("Joomla", ["CMS"], meta={"generator": r"Joomla"}, body=[r"/media/jui/", r"/templates/joomla"])
_sig("Squarespace", ["CMS"], body=[r"squarespace\.com", r"static\.squarespace\.com"])
_sig("Wix", ["CMS"], body=[r"wix\.com", r"static\.wixstatic\.com"])
_sig("Shopify", ["E-commerce"], body=[r"cdn\.shopify\.com", r"Shopify\.theme"], cookies=["_shopify_s"])
_sig("Magento", ["E-commerce"], body=[r"/static/version", r"mage/cookies"], cookies=["PHPSESSID"])
_sig("Ghost", ["CMS"], meta={"generator": r"Ghost"})

# --- JavaScript frameworks ---
_sig("React", ["JavaScript Framework"], body=[r"react(?:\.production|\.development|DOM)", r"__NEXT_DATA__"])
_sig("Next.js", ["JavaScript Framework"], headers={"x-powered-by": r"Next\.js"}, body=[r"__NEXT_DATA__", r"/_next/"])
_sig("Vue.js", ["JavaScript Framework"], body=[r"vue(?:\.runtime|\.global)", r"__vue__"])
_sig("Nuxt.js", ["JavaScript Framework"], body=[r"__NUXT__", r"/_nuxt/"])
_sig("Angular", ["JavaScript Framework"], body=[r"ng-version=", r"angular(?:\.min)?\.js"])
_sig("jQuery", ["JavaScript Library"], body=[r"jquery(?:\.min)?\.js"])
_sig("Bootstrap", ["CSS Framework"], body=[r"bootstrap(?:\.min)?\.(?:css|js)"])
_sig("Tailwind CSS", ["CSS Framework"], body=[r"tailwindcss", r"tailwind\."])

# --- CDN / Hosting ---
_sig("Cloudflare", ["CDN"], headers={"server": r"cloudflare", "cf-ray": r"."})
_sig("Amazon CloudFront", ["CDN"], headers={"x-amz-cf-id": r".", "via": r"cloudfront"})
_sig("Fastly", ["CDN"], headers={"via": r"varnish", "x-served-by": r"cache-"})
_sig("Akamai", ["CDN"], headers={"x-akamai-transformed": r"."})
_sig("Vercel", ["PaaS"], headers={"x-vercel-id": r".", "server": r"Vercel"})
_sig("Netlify", ["PaaS"], headers={"server": r"Netlify", "x-nf-request-id": r"."})
_sig("Heroku", ["PaaS"], headers={"via": r"vegur"})

# --- Analytics / Marketing ---
_sig("Google Analytics", ["Analytics"], body=[r"google-analytics\.com/(?:analytics|ga)\.js", r"googletagmanager\.com", r"gtag\("])
_sig("Google Tag Manager", ["Tag Manager"], body=[r"googletagmanager\.com/gtm\.js"])
_sig("Hotjar", ["Analytics"], body=[r"static\.hotjar\.com", r"hotjar\.com"])
_sig("Segment", ["Analytics"], body=[r"cdn\.segment\.com", r"analytics\.js"])

# --- Security ---
_sig("reCAPTCHA", ["Security"], body=[r"google\.com/recaptcha", r"grecaptcha"])
_sig("hCaptcha", ["Security"], body=[r"hcaptcha\.com"])
_sig("Cloudflare Turnstile", ["Security"], body=[r"challenges\.cloudflare\.com/turnstile"])

# --- Other ---
_sig("Google Fonts", ["Font"], body=[r"fonts\.googleapis\.com", r"fonts\.gstatic\.com"])
_sig("Font Awesome", ["Font"], body=[r"font-awesome", r"fontawesome"])
_sig("Stripe", ["Payment"], body=[r"js\.stripe\.com"])
_sig("PayPal", ["Payment"], body=[r"paypal\.com/sdk", r"paypalobjects\.com"])
_sig("Intercom", ["Live Chat"], body=[r"widget\.intercom\.io", r"intercomSettings"])
_sig("Zendesk", ["Live Chat"], body=[r"static\.zdassets\.com", r"zendesk"])
_sig("HubSpot", ["Marketing"], body=[r"js\.hs-scripts\.com", r"hubspot\.com"])
_sig("Salesforce", ["CRM"], body=[r"force\.com", r"salesforce\.com"])


async def check_tech_fingerprint(domain: str) -> TechFingerprintResult:
    """Detect technologies from HTTP response headers, cookies, and HTML body."""
    result = TechFingerprintResult(domain=domain)

    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            async with httpx.AsyncClient(
                timeout=_HTTP_TIMEOUT,
                follow_redirects=True,
                verify=False,  # noqa: S501
            ) as client:
                resp = await client.get(url)

            headers_lower = {k.lower(): v for k, v in resp.headers.items()}
            body = resp.text[:200_000]  # cap body scan at 200KB
            cookie_names = [c.lower() for c in resp.cookies.keys()]

            # Scan meta tags from HTML
            meta_tags: dict[str, str] = {}
            for match in re.finditer(
                r'<meta\s+[^>]*name=["\']([^"\']+)["\'][^>]*content=["\']([^"\']+)["\']',
                body[:50_000],
                re.I,
            ):
                meta_tags[match.group(1).lower()] = match.group(2)

            for sig in _TECH_SIGNATURES:
                matched = False
                version = None

                # Check headers
                for header_key, pattern in sig["headers"].items():
                    val = headers_lower.get(header_key, "")
                    m = pattern.search(val)
                    if m:
                        matched = True
                        if m.lastindex:
                            version = m.group(1)
                        break

                # Check meta tags
                if not matched:
                    for meta_key, pattern in sig["meta"].items():
                        val = meta_tags.get(meta_key, "")
                        m = pattern.search(val)
                        if m:
                            matched = True
                            if m.lastindex:
                                version = m.group(1)
                            break

                # Check body patterns
                if not matched:
                    for pattern in sig["body"]:
                        if pattern.search(body):
                            matched = True
                            break

                # Check cookies
                if not matched and sig["cookies"]:
                    for cookie_name in sig["cookies"]:
                        if cookie_name in cookie_names:
                            matched = True
                            break

                if matched:
                    entry: dict = {
                        "name": sig["name"],
                        "categories": sig["categories"],
                    }
                    if version:
                        entry["version"] = version
                    result.detected.append(entry)

            return result
        except httpx.RequestError:
            continue
        except Exception as exc:
            # Log but continue to HTTP fallback instead of returning early
            logger.debug("Non-request error on %s://%s: %s", scheme, domain, exc)
            continue

    result.error = "Domain not reachable"
    return result


# ---------------------------------------------------------------------------
# Tier 2: Certificate Transparency via crt.sh
# ---------------------------------------------------------------------------

_CRTSH_URL = "https://crt.sh/?q={domain}&output=json"


async def check_crtsh(domain: str) -> CrtShResult:
    """Query crt.sh CT logs for certificates issued to this domain."""
    result = CrtShResult(domain=domain)
    try:
        url = _CRTSH_URL.format(domain=f"%.{domain}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})

        if resp.status_code != 200:
            result.error = f"crt.sh returned {resp.status_code}"
            return result

        data = resp.json()
        result.cert_count = len(data)

        seen: set[str] = set()
        for entry in data:
            name_value = entry.get("name_value", "")
            for name in name_value.splitlines():
                name = name.strip().lstrip("*.")
                if name and name.endswith(domain) and name != domain:
                    seen.add(name)

        result.subdomains = sorted(seen)
    except Exception as exc:
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# Tier 2: Have I Been Pwned domain search
# ---------------------------------------------------------------------------


async def check_hibp(domain: str, api_key: str | None) -> HibpResult:
    """Search HIBP for breached accounts associated with this domain.

    Requires a paid HIBP API key (HIBP_API_KEY in config).
    Returns a skipped result with no error when key is absent.
    """
    result = HibpResult(domain=domain)
    if not api_key:
        result.skipped = True
        return result

    try:
        url = f"https://haveibeenpwned.com/api/v3/breacheddomain/{domain}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                headers={
                    "hibp-api-key": api_key,
                    "user-agent": "HackerTracker-SecurityPlatform/1.0",
                },
            )

        if resp.status_code == 404:
            # No breaches found — not an error
            return result
        if resp.status_code == 401:
            result.error = "Invalid HIBP API key"
            return result
        if resp.status_code != 200:
            result.error = f"HIBP returned {resp.status_code}"
            return result

        data = resp.json()
        # HIBP domain search returns {email: [breach_names]}
        all_breach_names: set[str] = set()
        for breach_list in data.values():
            all_breach_names.update(breach_list)

        result.breaches_found = len(data)
        result.breach_names = sorted(all_breach_names)
    except Exception as exc:
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# Convenience: run all Tier 1 checks concurrently
# ---------------------------------------------------------------------------


async def run_tier1_checks(
    domain: str,
) -> tuple[DnsCheckResult, HttpHeaderResult, SslCheckResult, TechFingerprintResult]:
    """Run DNS, HTTP header, SSL, and tech fingerprint checks concurrently."""
    return await asyncio.gather(
        check_dns(domain),
        check_http_headers(domain),
        check_ssl(domain),
        check_tech_fingerprint(domain),
    )


async def check_shodan(domain: str, api_key: str | None) -> ShodanHostResult:
    """Query Shodan for open ports, detected CVEs, and service info on this domain's IP.

    Requires SHODAN_API_KEY (100 free query credits/month).
    Results are cached per IP for 24 hours to conserve quota.
    """
    result = ShodanHostResult(domain=domain)
    if not api_key:
        result.skipped = True
        return result

    try:
        import dns.asyncresolver  # type: ignore[import-untyped]
        import dns.exception  # type: ignore[import-untyped]

        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = _DNS_TIMEOUT
        answers = await resolver.resolve(domain, "A")
        ip = str(answers[0])
        result.ip = ip
    except Exception:
        result.error = "Could not resolve domain to IP"
        return result

    # Check in-memory cache first
    cached = _shodan_cache.get(ip)
    if cached:
        return cached

    try:
        url = f"https://api.shodan.io/shodan/host/{ip}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"key": api_key})

        if resp.status_code == 404:
            # IP not in Shodan index — not an error
            _shodan_cache[ip] = result
            return result
        if resp.status_code == 401:
            result.error = "Invalid Shodan API key"
            return result
        if resp.status_code == 402:
            result.error = "Shodan query credits exhausted"
            return result
        if resp.status_code != 200:
            result.error = f"Shodan returned {resp.status_code}"
            return result

        data = resp.json()
        result.open_ports = sorted(data.get("ports", []))
        result.vulns = sorted(data.get("vulns", {}).keys())
        result.isp = data.get("isp")

        # Extract service product/version from each service banner
        services: list[dict] = []
        for svc in data.get("data", []):
            port = svc.get("port")
            product = svc.get("product")
            version = svc.get("version")
            if port and product:
                entry: dict = {"port": port, "product": product}
                if version:
                    entry["version"] = version
                services.append(entry)
        result.services = services[:20]  # cap at 20 services

        _shodan_cache[ip] = result
    except Exception as exc:
        result.error = str(exc)

    return result


async def check_otx(domain: str, api_key: str | None) -> OtxResult:
    """Query AlienVault OTX for threat intelligence pulses on this domain.

    Requires OTX_API_KEY (free — register at otx.alienvault.com).
    Returns a skipped result when no key is configured.
    """
    result = OtxResult(domain=domain)
    if not api_key:
        result.skipped = True
        return result

    try:
        url = f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/general"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                headers={
                    "X-OTX-API-KEY": api_key,
                    "User-Agent": "HackerTracker-SecurityPlatform/1.0",
                },
            )

        if resp.status_code == 400:
            # Domain not found in OTX — not an error
            return result
        if resp.status_code == 403:
            result.error = "Invalid OTX API key"
            return result
        if resp.status_code != 200:
            result.error = f"OTX returned {resp.status_code}"
            return result

        data = resp.json()
        result.pulse_count = data.get("pulse_info", {}).get("count", 0)
        result.reputation_score = data.get("reputation", None)

        # Extract malware family names from pulse tags
        malware_families: set[str] = set()
        for pulse in data.get("pulse_info", {}).get("pulses", [])[:20]:
            for tag in pulse.get("tags", []):
                # Filter to likely malware family names (short, no spaces)
                if tag and len(tag) <= 30 and " " not in tag:
                    malware_families.add(tag)
        result.malware_families = sorted(malware_families)[:15]
    except Exception as exc:
        result.error = str(exc)

    return result


async def run_tier2_checks(
    domain: str,
    hibp_api_key: str | None = None,
    shodan_api_key: str | None = None,
    otx_api_key: str | None = None,
) -> tuple[CrtShResult, HibpResult, ShodanHostResult, OtxResult]:
    """Run crt.sh, HIBP, Shodan, and OTX checks concurrently."""
    return await asyncio.gather(
        check_crtsh(domain),
        check_hibp(domain, hibp_api_key),
        check_shodan(domain, shodan_api_key),
        check_otx(domain, otx_api_key),
    )
