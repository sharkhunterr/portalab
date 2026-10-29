"""#273/#275: a portal not yet set up is set up from the local networks only — a visitor from the internet
(or one a reverse proxy that is not trusted brings, its local address vouching for anyone) gets the very
same answer as any address; the health checks likewise."""

import httpx
from fastapi import FastAPI

from tests.integration.identity.helpers import PASSWORD


def _from(app: FastAPI, host: str, forwarded: str | None = None) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(host, 1234))
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    return httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers)


async def test_the_internet_cannot_set_a_portal_up(app: FastAPI) -> None:
    wizard = {"login": "root", "password": PASSWORD, "display_name": "Root"}
    async with _from(app, "203.0.113.9") as outside:
        assert (await outside.get("/api/v1/admin/first-run")).status_code == 401
        assert (await outside.post("/api/v1/admin/first-run", json=wizard)).status_code == 401
        assert (await outside.get("/api/v1/admin/first-run/import/status")).status_code == 401
    # through a proxy nobody declared: its local address does not vouch for the visitor
    async with _from(app, "172.18.0.5", forwarded="203.0.113.9") as proxied:
        assert (await proxied.get("/api/v1/admin/first-run")).status_code == 401
        assert (await proxied.get("/healthz")).status_code == 401
    async with _from(app, "192.168.1.20") as lan:
        assert (await lan.get("/api/v1/admin/first-run")).json()["completed"] is False
        assert (await lan.get("/healthz")).status_code == 200
