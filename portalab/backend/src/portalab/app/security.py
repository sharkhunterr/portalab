"""Default-deny route protection (CD-002, contracts/api-conventions.md "AuthN").

Every API route must either declare a permission with :func:`require` or be explicitly marked :func:`public`.
A route with neither is refused at runtime by the app-wide :func:`enforce_default_deny` dependency, and the
route-table test fails in CI. Authentication (who is the caller) comes from a :class:`PrincipalResolver`;
the decision comes from the :class:`~portalab.core.authz_port.Authorizer` port (engine: spec 003).
"""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from fastapi import Depends, Request
from fastapi.routing import APIRoute

from portalab.core.authz_port import ANONYMOUS, Authorizer, Principal, ResourceRef
from portalab.core.errors import Forbidden, Unauthorized

PUBLIC_MARKER = "__portalab_public__"


class PrincipalResolver(Protocol):
    async def resolve(self, request: Request) -> Principal: ...


class AnonymousResolver:
    """Until authentication (spec 002) exists every caller is anonymous."""

    async def resolve(self, request: Request) -> Principal:
        return ANONYMOUS


def public[F: Callable[..., Any]](endpoint: F) -> F:
    """Mark an endpoint as intentionally reachable without authorization (health, sign-in)."""
    setattr(endpoint, PUBLIC_MARKER, True)
    return endpoint


class RequirePermission:
    """FastAPI dependency: the caller must hold ``permission`` (optionally on a resource)."""

    def __init__(
        self, permission: str, resource: Callable[[Request], ResourceRef | None] | None = None
    ) -> None:
        self.permission = permission
        self._resource = resource

    async def __call__(self, request: Request) -> Principal:
        principal = await current_principal(request)
        resource = self._resource(request) if self._resource else None
        authorizer: Authorizer = request.app.state.authorizer
        if await authorizer.is_allowed(principal, self.permission, resource):
            return principal
        if not principal.is_authenticated:
            raise Unauthorized()
        raise Forbidden()


def require(permission: str, resource: Callable[[Request], ResourceRef | None] | None = None) -> Any:
    """``Depends(...)`` declaring the permission a route needs."""
    return Depends(RequirePermission(permission, resource))


async def current_principal(request: Request) -> Principal:
    cached = getattr(request.state, "principal", None)
    if isinstance(cached, Principal):
        return cached
    resolver: PrincipalResolver = request.app.state.principal_resolver
    principal = await resolver.resolve(request)
    request.state.principal = principal
    return principal


def route_access(route: APIRoute) -> str | None:
    """``"public"``, the declared permission, or ``None`` when the route declares nothing (denied)."""
    if getattr(route.endpoint, PUBLIC_MARKER, False):
        return "public"
    for dependency in route.dependant.dependencies:
        call = dependency.call
        if isinstance(call, RequirePermission):
            return call.permission
    for declared in route.dependencies:
        if isinstance(declared.dependency, RequirePermission):
            return declared.dependency.permission
    return None


async def enforce_default_deny(request: Request) -> None:
    """App-wide dependency: refuse any route that declares neither ``public`` nor a permission."""
    route = request.scope.get("route")
    if isinstance(route, APIRoute) and route_access(route) is None:
        principal = await current_principal(request)
        if not principal.is_authenticated:
            raise Unauthorized()
        raise Forbidden()


AsyncEndpoint = Callable[..., Awaitable[Any]]
