"""002 T017 — session cookie flags, CSRF on unsafe methods, session rotation on login (fixation)."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.modules.identity.api.middleware import CSRF_COOKIE, SESSION_COOKIE
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
