"""021 T032 — security headers, body-size cap (413), rate limits per IP and per session (429), health
probes exempt."""

import httpx
import pytest

from portalab.app.main import create_app
from portalab.app.security import SlidingWindowLimiter
from portalab.modules.privacy.settings import SecurityConfig

pytestmark = pytest.mark.unit


def _app(config: SecurityConfig) -> object:
    return create_app(migration_heads=set(), static_dir=None, security_config=config)


async def _client(config: SecurityConfig) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(config)), base_url="https://portal.test")  # type: ignore[arg-type]


async def test_security_headers_on_every_response() -> None:
    async with await _client(SecurityConfig()) as client:
        for path in ("/healthz", "/api/v1/stream", "/api/v1/nope"):
            response = await client.get(path)
            assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["strict-transport-security"].startswith("max-age=")
            assert response.headers["referrer-policy"] == "no-referrer"


async def test_body_size_cap() -> None:
    async with await _client(SecurityConfig(max_body_bytes=100)) as client:
        response = await client.post(
            "/api/v1/auth/login", content=b"x" * 500, headers={"content-type": "application/json"}
        )
        assert response.status_code == 413 and response.json()["code"] == "request.too_large"


async def test_rate_limit_per_ip_and_health_exempt() -> None:
    config = SecurityConfig(rate_limit_per_ip_per_minute=3, rate_limit_per_user_per_minute=100)
    async with await _client(config) as client:
        statuses = [(await client.get("/api/v1/stream")).status_code for _ in range(5)]
        assert statuses[:3] == [401, 401, 401] and statuses[3:] == [429, 429]
        limited = await client.get("/api/v1/stream")
        assert int(limited.headers["retry-after"]) >= 1 and limited.json()["code"] == "rate_limited"
        assert (await client.get("/healthz")).status_code == 200


async def test_rate_limit_per_session() -> None:
    config = SecurityConfig(rate_limit_per_ip_per_minute=100, rate_limit_per_user_per_minute=2)
    async with await _client(config) as client:
        client.cookies.set("__Host-portalab_session", "abc")
        codes = [(await client.get("/api/v1/stream")).status_code for _ in range(3)]
    assert codes[-1] == 429


def test_sliding_window() -> None:
    now = [0.0]
    limiter = SlidingWindowLimiter(2, window=60, clock=lambda: now[0])
    assert limiter.hit("k") is None and limiter.hit("k") is None
    assert limiter.hit("k") == pytest.approx(60)
    now[0] = 61
    assert limiter.hit("k") is None
