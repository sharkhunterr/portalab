"""021 T032 — security headers, body-size cap (413), rate limits per IP and per session (429), health
probes and static assets exempt."""

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
            # #315: frames from the portal itself and YouTube's privacy-enhanced player only
            assert (
                "frame-src 'self' https://www.youtube-nocookie.com;"
                in response.headers["content-security-policy"]
            )
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
        # 027: static assets (dozens of chunks per page load) are not rate limited, only the API is
        statics = [(await client.get("/assets/app.js")).status_code for _ in range(5)]
        assert 429 not in statics
        # nor the translation catalogs read on every full load; writes to the same prefix still count
        catalogs = [(await client.get("/api/v1/i18n/catalogs/core")).status_code for _ in range(5)]
        assert 429 not in catalogs
        assert (await client.post("/api/v1/i18n/catalogs/core")).status_code == 429


async def test_rate_limit_per_session() -> None:
    config = SecurityConfig(rate_limit_per_ip_per_minute=100, rate_limit_per_user_per_minute=2)
    async with await _client(config) as client:
        client.cookies.set("__Host-portalab_session", "abc")
        codes = [(await client.get("/api/v1/stream")).status_code for _ in range(3)]
    assert codes[-1] == 429


async def test_pictures_count_on_their_own_budget() -> None:
    """#305: a page rich in pictures (posters, portraits, avatars) never spends the member's budget — a
    reload's session check still answers — and the pictures have a budget of their own, four times larger."""
    config = SecurityConfig(rate_limit_per_ip_per_minute=100, rate_limit_per_user_per_minute=2)
    async with await _client(config) as client:
        client.cookies.set("__Host-portalab_session", "abc")
        pictures = [
            "/api/v1/media/metadata-images?path=/a.jpg",
            "/api/v1/media/images/01a10781-8e15-754c-8e92-273615b9458e",
            "/api/v1/media/person/portrait?name=x",
            "/api/v1/users/01a10781-8e15-754c-8e92-273615b9458e/avatar",
        ]
        codes = [(await client.get(pictures[i % 4])).status_code for i in range(8)]
        assert 429 not in codes
        assert (await client.get("/api/v1/me")).status_code != 429
        assert (await client.get(pictures[0])).status_code == 429  # 2 x 4 pictures a minute


def test_sliding_window() -> None:
    now = [0.0]
    limiter = SlidingWindowLimiter(2, window=60, clock=lambda: now[0])
    assert limiter.hit("k") is None and limiter.hit("k") is None
    assert limiter.hit("k") == pytest.approx(60)
    now[0] = 61
    assert limiter.hit("k") is None


async def test_an_answer_in_json_cannot_be_embedded_by_another_site() -> None:
    """Issue 400: JSON (and problem details) is read by the portal's own pages only; pictures and streams
    stay embeddable (a Chromecast plays the portal's streams from Google's receiver page)."""
    from portalab.app.security import _json

    async with await _client(SecurityConfig()) as client:
        for path in ("/api/v1/nope", "/api/v1/auth/oidc"):
            response = await client.get(path)
            assert response.headers["content-type"].split(";")[0].endswith("json"), path
            assert response.headers["cross-origin-resource-policy"] == "same-origin", path
    assert _json([(b"content-type", b"application/problem+json")]) and _json(
        [(b"Content-Type", b"application/json; charset=utf-8")]
    )
    assert not _json([(b"content-type", b"image/webp")]) and not _json([(b"content-type", b"video/mp4")])
