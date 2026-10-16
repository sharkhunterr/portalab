"""028 (SC-005, issue 135): without a session, the portal answers only signing in, the single sign-on, the
single-purpose links and the sign-in page's words — every other address, existing or not, gets the very same
answer, so a visitor learns nothing of what the portal holds."""

import httpx
import pytest

from portalab.app.main import create_app
from portalab.app.security import ANONYMOUS_PATHS, anonymous_allowed
from portalab.core.authorization import api_routes
from portalab.core.db import Database
from portalab.modules.privacy.settings import SecurityConfig

pytestmark = pytest.mark.integration

UNKNOWN = (
    "/api/v1/does-not-exist",
    "/api/v1/admin/secret-page",
    "/api/v1/admin/visuals/x/1.0.0/publish",
    "/api/v1/%2e%2e/%2e%2e/etc/passwd",
    "/api/v1/users/00000000-0000-0000-0000-000000000000/profile",
)


async def test_a_visitor_reaches_nothing_but_signing_in(database: Database, heads: set[str]) -> None:
    limits = SecurityConfig(rate_limit_per_ip_per_minute=100_000, rate_limit_per_user_per_minute=100_000)
    app = create_app(database=database, migration_heads=heads, security_config=limits)
    app.state.intrusion_guard.enabled = False  # probing every route on purpose (the guard is tested apart)
    answers: set[bytes] = set()
    checked = 0
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for route in api_routes(app.routes):
            if anonymous_allowed(route.path) or route.path.startswith(("/healthz", "/readyz", "/metrics")):
                continue
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                response = await client.request(method, route.path)
                assert response.status_code == 401, (method, route.path, response.text)
                answers.add(response.content)
                checked += 1
        for path in UNKNOWN:
            for method in ("GET", "POST", "DELETE"):
                response = await client.request(method, path)
                assert response.status_code == 401, (method, path)
                answers.add(response.content)
    assert checked > 200
    assert len(answers) == 1, answers  # one answer, word for word, whatever the address


def test_the_allow_list_is_the_sign_in_and_nothing_else() -> None:
    assert all(p.startswith(("/api/v1/auth/", "/api/v1/admin/first-run")) for p in ANONYMOUS_PATHS)
    assert anonymous_allowed("/api/v1/i18n/catalogs/auth")
    assert not anonymous_allowed("/api/v1/i18n/catalogs/admin")
    assert not anonymous_allowed("/api/v1/terms")
    assert not anonymous_allowed("/api/v1/visuals/sandbox")
    assert anonymous_allowed("/media/some-client-route")  # the SPA's pages: the sign-in page
