"""T022 — default-deny: every non-allow-listed route refuses without an authorizer grant.

The checks are generated from the application's route table, so a newly added route is covered automatically.
"""

from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute

from portalab.app.main import create_app
from portalab.app.security import api_routes, public, require, route_access
from portalab.core.authz_port import DenyAllAuthorizer, Principal, ResourceRef
from portalab.core.db import Database

ALLOW_LISTED = {
    "/healthz",
    "/readyz",
    # sign-in flows (spec 002): reachable before authentication by definition
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/register",
    "/api/v1/auth/verify",
    "/api/v1/auth/deletion/cancel",
    "/api/v1/admin/first-run",  # spec 020: public only until the sole Admin exists
}


class AllowAll:
    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return True


class FixedPrincipal:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve(self, request: Request) -> Principal:
        return self.principal


def _with_probe_routes(app: FastAPI) -> FastAPI:
    @app.get("/api/v1/_probe/undeclared")
    async def undeclared() -> dict[str, str]:
        return {"leak": "should never be reachable"}

    @app.post("/api/v1/_probe/undeclared")
    async def undeclared_post() -> dict[str, str]:
        return {"leak": "should never be reachable"}

    @app.get("/api/v1/_probe/guarded", dependencies=[require("probe.read")])
    async def guarded() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/api/v1/_probe/public")
    @public
    async def open_route() -> dict[str, str]:
        return {"ok": "public"}

    return app


def _api_routes(app: FastAPI) -> list[APIRoute]:
    return api_routes(app.routes)


async def _call(app: FastAPI, route: APIRoute, method: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, route.path)


def test_production_routes_all_declare_their_access(heads: set[str]) -> None:
    app = create_app(migration_heads=heads)
    routes = _api_routes(app)
    assert len(routes) > 10  # health, stream and the identity API are all discovered
    undeclared = [r.path for r in routes if route_access(r) is None]
    assert undeclared == [], f"routes without require()/public: {undeclared}"
    public_paths = {r.path for r in _api_routes(app) if route_access(r) == "public"}
    assert public_paths <= ALLOW_LISTED


@pytest.mark.parametrize("authenticated", [False, True])
async def test_every_non_public_route_is_denied_by_default(
    database: Database, heads: set[str], authenticated: bool
) -> None:
    principal = Principal(user_id=uuid4()) if authenticated else Principal()
    app = _with_probe_routes(
        create_app(
            database=database,
            migration_heads=heads,
            principal_resolver=FixedPrincipal(principal),
            authorizer=DenyAllAuthorizer(),  # structure test; real grants: tests/security/authz matrix
        )
    )
    expected = 403 if authenticated else 401
    checked = 0
    for route in _api_routes(app):
        if route_access(route) == "public":
            continue
        for method in route.methods:
            response = await _call(app, route, method)
            assert response.status_code == expected, (method, route.path, response.text)
            assert response.headers["content-type"].startswith("application/problem+json")
            assert "leak" not in response.text
            checked += 1
    assert checked >= 3


async def test_undeclared_route_stays_denied_even_if_authorizer_allows_everything(
    database: Database, heads: set[str]
) -> None:
    app = _with_probe_routes(
        create_app(
            database=database,
            migration_heads=heads,
            authorizer=AllowAll(),
            principal_resolver=FixedPrincipal(Principal(user_id=uuid4())),
        )
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/_probe/undeclared")).status_code == 403
        granted = await client.get("/api/v1/_probe/guarded")
        assert granted.status_code == 200
        assert granted.json() == {"ok": "yes"}
        assert (await client.get("/api/v1/_probe/public")).status_code == 200


async def test_unknown_route_is_a_problem_document(database: Database, heads: set[str]) -> None:
    app = create_app(database=database, migration_heads=heads)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.headers["X-Correlation-Id"]
