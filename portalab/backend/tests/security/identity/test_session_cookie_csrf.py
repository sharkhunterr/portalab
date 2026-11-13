"""002 T017 — session cookie flags, CSRF on unsafe methods, session rotation on login (fixation)."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.modules.identity.api.middleware import (
    CSRF_COOKIE,
    PLAIN_CSRF_COOKIE,
    PLAIN_SESSION_COOKIE,
    SESSION_COOKIE,
)
from portalab.modules.identity.models import UserSession
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration


@pytest.fixture
async def alice(app: FastAPI) -> None:
    await create_user(module_of(app), "alice")


def _cookie_header(response: httpx.Response, name: str) -> str:
    headers = [value for value in response.headers.get_list("set-cookie") if value.startswith(name + "=")]
    assert len(headers) == 1, response.headers.get_list("set-cookie")
    return headers[0].lower()


@pytest.mark.usefixtures("alice")
async def test_cookie_flags(client: httpx.AsyncClient) -> None:
    response = await login(client, "alice")
    session_cookie = _cookie_header(response, SESSION_COOKIE)
    for flag in ("httponly", "secure", "samesite=lax", "path=/"):
        assert flag in session_cookie
    assert "domain=" not in session_cookie  # required by the __Host- prefix
    csrf_cookie = _cookie_header(response, CSRF_COOKIE)
    assert "secure" in csrf_cookie and "httponly" not in csrf_cookie
    assert SESSION_COOKIE.startswith("__Host-")


@pytest.mark.usefixtures("alice")
async def test_unsafe_methods_need_the_csrf_header(client: httpx.AsyncClient) -> None:
    response = await login(client, "alice")
    token = client.headers.pop("X-CSRF-Token")
    assert token == response.json()["csrf_token"]
    assert (await client.get("/api/v1/me")).status_code == 200  # safe method: no header needed

    missing = await client.patch("/api/v1/me/profile", json={"fields": {"bio": {"value": "hi"}}})
    assert missing.status_code == 403
    assert missing.json()["code"] == "auth.csrf_failed"

    wrong = await client.patch(
        "/api/v1/me/profile", json={"fields": {"bio": {"value": "hi"}}}, headers={"X-CSRF-Token": "0" * 64}
    )
    assert wrong.status_code == 403

    ok = await client.patch(
        "/api/v1/me/profile", json={"fields": {"bio": {"value": "hi"}}}, headers={"X-CSRF-Token": token}
    )
    assert ok.status_code == 200

    logout_without = await client.post("/api/v1/auth/logout")
    assert logout_without.status_code == 403


@pytest.mark.usefixtures("alice")
async def test_login_rotates_any_presented_session(app: FastAPI, client: httpx.AsyncClient) -> None:
    await login(client, "alice")
    first = client.cookies.get(SESSION_COOKIE)
    await login(client, "alice")
    second = client.cookies.get(SESSION_COOKIE)
    assert first and second and first != second
    async with module_of(app).ctx.database.session() as session:
        rows = (await session.execute(select(UserSession).order_by(UserSession.created_at))).scalars().all()
    assert [row.revoke_reason for row in rows] == ["rotated", None]

    stale = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
    async with stale:
        stale.cookies.set(SESSION_COOKIE, first)
        assert (await stale.get("/api/v1/me")).status_code == 401


@pytest.mark.usefixtures("alice")
async def test_logout_revokes_and_clears_cookies(client: httpx.AsyncClient) -> None:
    await login(client, "alice")
    token = client.cookies.get(SESSION_COOKIE)
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    cleared = _cookie_header(response, SESSION_COOKIE)
    assert "max-age=0" in cleared or "expires=" in cleared
    client.cookies.set(SESSION_COOKIE, token or "")
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_garbage_cookie_is_anonymous(client: httpx.AsyncClient) -> None:
    client.cookies.set(SESSION_COOKIE, "not-a-session")
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def _session_names(response: httpx.Response) -> list[str]:
    return sorted(value.split("=", 1)[0] for value in response.headers.get_list("set-cookie"))


@pytest.mark.usefixtures("alice")
async def test_plain_http_from_the_local_network_keeps_the_session(app: FastAPI) -> None:
    """#395: a portal reached at ``http://192.168.1.30:8445`` — a browser drops every ``Secure`` cookie
    there, so the session went nowhere and the setup wizard failed with « Authentication required »."""
    transport = httpx.ASGITransport(app=app, client=("192.168.1.50", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://192.168.1.30:8445") as http:
        response = await login(http, "alice")
        assert _session_names(response) == [PLAIN_CSRF_COOKIE, PLAIN_SESSION_COOKIE]
        session_cookie = _cookie_header(response, PLAIN_SESSION_COOKIE)
        assert "httponly" in session_cookie and "secure" not in session_cookie
        assert "secure" not in _cookie_header(response, PLAIN_CSRF_COOKIE)
        assert (await http.get("/api/v1/me")).status_code == 200
        refused = await http.patch(
            "/api/v1/me/profile", json={"fields": {"bio": {"value": "hi"}}}, headers={"X-CSRF-Token": ""}
        )
        assert refused.status_code == 403  # the double submit still holds
        assert (await http.post("/api/v1/auth/logout")).status_code == 204
        assert (await http.get("/api/v1/me")).status_code == 401


@pytest.mark.usefixtures("alice")
@pytest.mark.parametrize(
    ("client", "headers"),
    [
        (("203.0.113.7", 50000), {}),  # plain HTTP from the internet
        (("192.168.1.2", 50000), {"X-Forwarded-For": "203.0.113.7"}),  # through a proxy not trusted
    ],
)
async def test_plain_http_from_elsewhere_keeps_the_strict_cookies(
    app: FastAPI, client: tuple[str, int], headers: dict[str, str]
) -> None:
    transport = httpx.ASGITransport(app=app, client=client)
    async with httpx.AsyncClient(transport=transport, base_url="http://portal.test", headers=headers) as http:
        response = await login(http, "alice")
        assert _session_names(response) == [CSRF_COOKIE, SESSION_COOKIE]
        assert "secure" in _cookie_header(response, SESSION_COOKIE)


@pytest.mark.usefixtures("alice")
async def test_a_plain_cookie_never_counts_over_https(app: FastAPI) -> None:
    """#395: the plain session cookie carries no ``__Host-`` guarantee — over HTTPS it is ignored, so a
    cookie planted by a sibling subdomain or a network attacker cannot sign anyone into its session."""
    lan = httpx.ASGITransport(app=app, client=("192.168.1.50", 50000))
    async with httpx.AsyncClient(transport=lan, base_url="http://192.168.1.30:8445") as http:
        planted = (await login(http, "alice")).cookies[PLAIN_SESSION_COOKIE]
    secure = httpx.ASGITransport(app=app, client=("192.168.1.50", 50000))
    async with httpx.AsyncClient(transport=secure, base_url="https://portal.test") as https:
        https.cookies.set(PLAIN_SESSION_COOKIE, planted)
        assert (await https.get("/api/v1/me")).status_code == 401


@pytest.mark.usefixtures("alice")
async def test_sign_in_audited_csrf_failure_logged_api_not_cached_cache_cleared_at_sign_out(
    client: httpx.AsyncClient, app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    """Issue 405: a successful sign-in is audited (how, from which network); a CSRF failure is logged; an
    API answer in JSON is never cached; signing out clears the browser's cache of the portal."""
    await login(client, "alice")
    [entry] = [r for r in module_of(app).ctx.audit.records if r.action == "auth.signed_in"]
    assert entry.context["method"] == "password"
    me = await client.get("/api/v1/me")
    assert me.headers["cache-control"] == "no-store"
    token = client.headers.pop("X-CSRF-Token")
    with caplog.at_level("WARNING"):
        assert (await client.patch("/api/v1/me/profile", json={"fields": {}})).status_code == 403
    assert any("CSRF check failed" in r.getMessage() for r in caplog.records)
    assert token not in caplog.text
    out = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token})
    assert out.status_code == 204 and out.headers["clear-site-data"] == '"cache"'
