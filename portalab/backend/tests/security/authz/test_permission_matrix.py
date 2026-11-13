"""003 T016 — permission matrix generated from the application's route table, with the real engine.

Every route is protected by ``require()`` or explicitly allow-listed as public; anonymous callers get 401 on
every protected route; a plain user (base User role only) gets 403 on every route whose permission the User
role does not hold, and is never refused on the ones it does hold.
"""

import re

import httpx
import pytest
from fastapi import FastAPI

import portalab.app.main  # noqa: F401 — imports every module, so their permissions are declared
from portalab.app.security import api_routes, route_access
from portalab.core.permissions import default_permissions
from portalab.modules.authz.catalog.core_permissions import CORE_PERMISSIONS
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration

PUBLIC = {
    "/healthz",
    "/readyz",
    "/api/v1/auth/login",
    "/api/v1/auth/login/mfa",  # issue 408: the sign-in's second step
    "/api/v1/auth/logout",
    "/api/v1/auth/register",
    "/api/v1/auth/verify",
    "/api/v1/auth/deletion/cancel",
    "/api/v1/auth/oidc",  # 027: the single sign-on (whether offered, start, the provider's way back)
    "/api/v1/auth/oidc/start",
    "/api/v1/auth/oidc/callback",
    "/api/v1/media/remote/{ticket}/session/{path:path}",  # 027 (#11): a cast device's stream
    "/api/v1/newsletters/pictures/{token}/{image_id}",  # #316: an e-mailed edition's pictures
    "/api/v1/admin/first-run",  # spec 020: public only until the sole Admin exists
    "/api/v1/admin/first-run/import",  # issue 247: the arrival wizard brings a backup in (until set up)
    "/api/v1/admin/first-run/import/upload",
    "/api/v1/admin/first-run/import/inspect",
    "/api/v1/admin/first-run/import/status",
    "/api/v1/auth/terms",  # issue 157: only while the administrators offer the terms on the sign-in page
    "/api/v1/auth/site",  # issue 159: the site's name, slogan and images, on the sign-in page
    "/api/v1/auth/site/logo",
    "/api/v1/auth/site/icon",
    "/api/v1/auth/site/manifest",
    "/api/v1/i18n/public/languages",  # issue 246: the arrival wizard and sign-in in the visitor's language
    "/api/v1/i18n/public/catalogs/{namespace}",  # only the pre-sign-in screens' catalogs (core, account)
    "/metrics",  # spec 025: disabled by default; own token/permission check
}
USER_ROLE = {
    key
    for key, _d, _s, _r, _c, roles in CORE_PERMISSIONS
    if any((role if isinstance(role, str) else role[0]) == "user" for role in roles)
} | {  # module-declared permissions granted to the User role by default (e.g. search.use, spec 008)
    declaration.key
    for declaration in default_permissions.all()
    if any(grant.role == "user" for grant in declaration.default_grants)
}
SAMPLE_ID = "00000000-0000-7000-8000-000000000000"


def _protected(app: FastAPI) -> list[tuple[str, str, str]]:
    rows = []
    for route in api_routes(app.routes):
        access = route_access(route)
        assert access is not None, f"{route.path} declares neither require() nor public"
        if access == "public":
            assert route.path in PUBLIC, route.path
            continue
        path = re.sub(r"\{[a-z_]+_id\}", SAMPLE_ID, route.path)
        path = path.replace("{step}", "profile").replace("{role_key}", "editor").replace("{group_key}", "ops")
        rows.extend((method, path, access) for method in sorted(route.methods))
    return rows


def test_every_route_is_protected_or_allow_listed(app: FastAPI) -> None:
    rows = _protected(app)
    assert len(rows) > 40


async def test_anonymous_gets_401_everywhere(app: FastAPI, client: httpx.AsyncClient) -> None:
    app.state.intrusion_guard.enabled = False  # 028: an address listing the administration would be blocked
    for method, path, _ in _protected(app):
        response = await client.request(method, path, json={})
        assert response.status_code == 401, (method, path, response.text)


async def test_plain_user_matrix(app: FastAPI, client: httpx.AsyncClient) -> None:
    # issue 1: this test knocks on every route a member may not open — on purpose; the intrusion guard (which
    # would block such a member) is tested on its own (tests/unit/identity/test_intrusion_guard.py)
    app.state.intrusion_guard.enabled = False
    await create_user(module_of(app), "plain")
    assert (await login(client, "plain")).status_code == 200
    for method, path, permission in _protected(app):
        if path == "/api/v1/stream":
            continue  # long-lived SSE response; covered by tests/integration/test_stream.py
        response = await client.request(method, path, json={})
        if permission in USER_ROLE:
            assert response.status_code not in (401, 403), (method, path, response.text)
        else:
            assert response.status_code == 403, (method, path, permission, response.text)
