"""Default-deny enforcement at the composition root (CD-002).

The route-level dependencies (:func:`require`, :func:`public`, …) live in :mod:`portalab.core.authorization`
so modules can use them; this module adds the app-wide :func:`enforce_default_deny` guard that refuses any
route declaring neither, and re-exports the dependencies for the composition root.
"""

from fastapi import Request
from fastapi.routing import APIRoute

from portalab.core.authorization import (
    PUBLIC_MARKER,
    AnonymousResolver,
    PrincipalResolver,
    RequirePermission,
    api_routes,
    current_principal,
    public,
    require,
    route_access,
)
from portalab.core.errors import Forbidden, Unauthorized

__all__ = [
    "PUBLIC_MARKER",
    "AnonymousResolver",
    "PrincipalResolver",
    "RequirePermission",
    "api_routes",
    "current_principal",
    "enforce_default_deny",
    "public",
    "require",
    "route_access",
]


async def enforce_default_deny(request: Request) -> None:
    """App-wide dependency: refuse any route that declares neither ``public`` nor a permission."""
    route = request.scope.get("route")
    if isinstance(route, APIRoute) and route_access(route) is None:
        principal = await current_principal(request)
        if not principal.is_authenticated:
            raise Unauthorized()
        raise Forbidden()
