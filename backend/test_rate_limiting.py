"""
Standalone rate-limiting smoke tests.
No database required — uses a minimal FastAPI app that mirrors the real
limiter/handler setup from app/main.py.

Run: python3 test_rate_limiting.py
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

# ── replicate the real limiter setup ──────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    try:
        inner = exc.limit.limit
        retry_after = str(inner.GRANULARITY.seconds * (inner.multiples or 1))
    except (AttributeError, TypeError):
        retry_after = "60"
    response = JSONResponse(
        status_code=429,
        content={"error": "Too Many Requests", "detail": str(exc.detail)},
    )
    response.headers["Retry-After"] = retry_after
    return response


app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


@app.post("/auth/login")
@limiter.limit("10/minute")
async def mock_login(request: Request):
    return {"status": "ok"}


@app.get("/api/data")
@limiter.limit("60/minute")
async def mock_data(request: Request):
    return {"data": "ok"}


# ── tests ─────────────────────────────────────────────────────────────────────

client = TestClient(app, raise_server_exceptions=False)

PASS = "✓"
FAIL = "✗"


def check(label, condition):
    mark = PASS if condition else FAIL
    print(f"  {mark}  {label}")
    if not condition:
        raise AssertionError(label)


def test_auth_rate_limit():
    print("\n── Auth endpoint  (limit: 10/minute) ──────────────────────────")
    codes = []
    for _ in range(12):
        r = client.post("/auth/login")
        codes.append(r.status_code)

    under_limit = codes[:10]
    over_limit  = codes[10:]

    check("Requests 1-10 return 200",  all(c == 200 for c in under_limit))
    check("Requests 11-12 return 429", all(c == 429 for c in over_limit))

    # Inspect the last 429 response in detail
    r429 = client.post("/auth/login")
    check("Status code is 429",              r429.status_code == 429)
    check("Content-Type is application/json", "application/json" in r429.headers.get("content-type", ""))

    body = r429.json()
    check('Body has "error" key',            "error" in body)
    check('body["error"] == "Too Many Requests"', body["error"] == "Too Many Requests")
    check('Body has "detail" key',           "detail" in body)
    check("detail mentions the limit rule",  "10" in body["detail"] and "minute" in body["detail"])

    retry_after = r429.headers.get("retry-after")
    check("Retry-After header is present",   retry_after is not None)
    check("Retry-After is a number",         retry_after is not None and retry_after.isdigit())
    check("Retry-After > 0",                 retry_after is not None and int(retry_after) > 0)

    print(f"\n     429 body:          {body}")
    print(f"     Retry-After value: {retry_after}s")


def test_data_rate_limit():
    print("\n── Data endpoint  (limit: 60/minute) ──────────────────────────")

    # Burn through the first 60 to verify they pass
    codes = [client.get("/api/data").status_code for _ in range(62)]
    first_60 = codes[:60]
    over     = codes[60:]

    check("Requests 1-60 return 200",  all(c == 200 for c in first_60))
    check("Requests 61-62 return 429", all(c == 429 for c in over))

    r429 = client.get("/api/data")
    retry_after = r429.headers.get("retry-after")
    check("Retry-After header present on data 429", retry_after is not None)
    print(f"\n     Retry-After value: {retry_after}s")


def test_limits_are_independent():
    """Verify auth and data counters are tracked separately.

    Strategy: use a fresh app with a key_func that reads X-Test-Client-ID so
    each logical 'client' gets its own counter bucket, then confirm that
    exhausting the auth limit (10/min) does NOT affect the data counter.
    """
    print("\n── Auth and data limits are independent ───────────────────────")

    def client_id_key(request: Request) -> str:
        return request.headers.get("X-Test-Client-ID", "default")

    iso_limiter = Limiter(key_func=client_id_key)

    iso_app = FastAPI()
    iso_app.state.limiter = iso_limiter
    iso_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    iso_app.add_middleware(SlowAPIMiddleware)

    @iso_app.post("/auth/login")
    @iso_limiter.limit("10/minute")
    async def iso_login(request: Request):
        return {"ok": True}

    @iso_app.get("/api/data")
    @iso_limiter.limit("60/minute")
    async def iso_data(request: Request):
        return {"ok": True}

    iso_client = TestClient(iso_app, raise_server_exceptions=False)

    # Exhaust the auth limit for client-A
    for _ in range(10):
        iso_client.post("/auth/login", headers={"X-Test-Client-ID": "client-A"})
    auth_r = iso_client.post("/auth/login", headers={"X-Test-Client-ID": "client-A"})
    check("Auth is exhausted for client-A (429)", auth_r.status_code == 429)

    # Data endpoint for the same client-A should still have its own fresh counter
    data_r = iso_client.get("/api/data", headers={"X-Test-Client-ID": "client-A"})
    check("Hitting auth limit does NOT affect data counter (200)", data_r.status_code == 200)

    # And a completely different client-B is unaffected by client-A's auth usage
    other_r = iso_client.post("/auth/login", headers={"X-Test-Client-ID": "client-B"})
    check("client-B auth counter is independent of client-A (200)", other_r.status_code == 200)


def test_retry_after_is_integer_seconds():
    print("\n── Retry-After format (integer seconds for SPA parsability) ───")
    # exhaust auth on a distinct IP
    spike = TestClient(app, raise_server_exceptions=False, headers={"X-Forwarded-For": "10.0.0.3"})
    for _ in range(11):
        spike.post("/auth/login")
    r429 = spike.post("/auth/login")
    retry_after = r429.headers.get("retry-after", "")
    check("Retry-After is a plain integer string (not HTTP-date)", retry_after.isdigit())
    check("Retry-After parses to >= 1 second",                     int(retry_after) >= 1)


# ── run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    passed = failed = 0
    for fn in [test_auth_rate_limit, test_data_rate_limit,
               test_limits_are_independent, test_retry_after_is_integer_seconds]:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"\n  {FAIL}  FAILED: {e}")
            failed += 1

    print(f"\n{'='*55}")
    print(f"  {passed} test(s) passed   {failed} test(s) failed")
    print(f"{'='*55}\n")
    raise SystemExit(1 if failed else 0)
