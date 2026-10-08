"""002 T048 — permission matrix generated from the route table (deny-by-default).

Every identity route declares either ``public`` (sign-in flows only) or one permission; anonymous callers get
401 and authenticated callers lacking the permission get 403 on every protected route. Roles are not stored
by identity: they are resolved by the authorization module (here its stand-in ``RoleAuthorizer``).
"""

import re

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from portalab.core.authorization import api_routes, route_access
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration

PUBLIC_ROUTES = {
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/register",
    "/api/v1/auth/verify",
    "/api/v1/auth/deletion/cancel",
    "/api/v1/auth/oidc",  # 027: the single sign-on (whether offered, start, the provider's way back)
    "/api/v1/auth/oidc/start",
    "/api/v1/auth/oidc/callback",
    "/api/v1/terms",  # 027: the terms of use in force (the sign-in page links them)
}

EXPECTED_PERMISSIONS = {
    ("GET", "/api/v1/me"): "users.self.manage",
    ("PATCH", "/api/v1/me/profile"): "users.self.manage",
    ("PUT", "/api/v1/me/avatar"): "users.self.manage",
    ("DELETE", "/api/v1/me/avatar"): "users.self.manage",
    ("GET", "/api/v1/me/onboarding"): "users.self.manage",
    ("POST", "/api/v1/me/onboarding/{step}/complete"): "users.self.manage",
    ("POST", "/api/v1/me/deletion"): "users.self.manage",
    ("DELETE", "/api/v1/me/deletion"): "users.self.manage",
    ("POST", "/api/v1/me/export"): "users.self.manage",
    ("GET", "/api/v1/me/export/{export_id}"): "users.self.manage",
    ("GET", "/api/v1/me/export/{export_id}/content"): "users.self.manage",
    ("GET", "/api/v1/users/{user_id}/profile"): "users.read",
    ("GET", "/api/v1/users/{user_id}/avatar"): "users.read",
    ("GET", "/api/v1/users"): "users.manage",
    ("POST", "/api/v1/users"): "users.manage",
    ("PATCH", "/api/v1/users/{user_id}"): "users.manage",
    ("POST", "/api/v1/users/{user_id}/verification"): "users.manage",
    ("POST", "/api/v1/users/{user_id}/suspend"): "users.manage",
    ("POST", "/api/v1/users/{user_id}/reactivate"): "users.manage",
    ("POST", "/api/v1/users/{user_id}/deletion"): "users.manage",
    ("DELETE", "/api/v1/users/{user_id}/deletion"): "users.manage",
    ("POST", "/api/v1/admin/transfer"): "users.admin.transfer",
}

SAMPLE_ID = "00000000-0000-7000-8000-000000000000"


def _identity_routes(app: FastAPI) -> list[tuple[str, APIRoute]]:
    routes = []
    for route in api_routes(app.routes):
        if "identity" in " ".join(str(tag) for tag in route.tags):
            routes.extend((method, route) for method in sorted(route.methods))
    return routes


def _concrete(path: str) -> str:
    return re.sub(r"\{(user_id|export_id)\}", SAMPLE_ID, path).replace("{step}", "profile")


def test_the_matrix_covers_every_identity_route(app: FastAPI) -> None:
    declared = {}
    for method, route in _identity_routes(app):
        access = route_access(route)
        assert access is not None, f"{method} {route.path} declares no access"
        if access == "public":
            assert route.path in PUBLIC_ROUTES, route.path
        else:
            declared[(method, route.path)] = access
    assert declared == EXPECTED_PERMISSIONS


async def test_anonymous_callers_get_401_everywhere(app: FastAPI, client: httpx.AsyncClient) -> None:
    for (method, path), _ in EXPECTED_PERMISSIONS.items():
        response = await client.request(method, _concrete(path), json={})
        assert response.status_code == 401, (method, path, response.text)


async def test_users_without_the_permission_get_403(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    user_id = await create_user(module, "plain")
    await login(client, "plain")
    harness_authorizer = app.state.authorizer
    harness_authorizer.denied = {"users.self.manage", "users.read"}
    for (method, path), _ in EXPECTED_PERMISSIONS.items():
        response = await client.request(method, _concrete(path), json={})
        assert response.status_code == 403, (method, path, response.text)
    harness_authorizer.denied = set()
    assert user_id
