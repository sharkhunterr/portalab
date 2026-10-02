"""003 T010 — every permission referenced by a route ``require()`` is declared in the catalog."""

import pytest

from portalab.app.main import create_app
from portalab.app.security import api_routes, route_access
from portalab.core.permissions import default_permissions
from portalab.modules.authz.catalog import core_permissions  # noqa: F401 — declares the core catalog

pytestmark = pytest.mark.boundary


def test_route_permissions_are_declared() -> None:
    app = create_app(migration_heads=set(), static_dir=None)
    used = {
        access for route in api_routes(app.routes) if (access := route_access(route)) not in (None, "public")
    }
    assert used, "no protected route found"
    assert sorted(used - default_permissions.keys()) == []
