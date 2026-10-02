"""Route-level authorization dependencies usable by every module (CD-002, api-conventions "AuthN").

Every API route must either declare a permission with :func:`require` or be explicitly marked
:func:`public`.
Authentication (who is the caller) comes from the :class:`PrincipalResolver` installed on the application
(identity's session resolver, spec 002); the decision comes from the
:class:`~portalab.core.authz_port.Authorizer` port (engine: spec 003). Ordering rule: *authorize, then filter*
— visibility (spec 021) is applied to the data after ``require()`` allowed the action.
"""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Protocol

from fastapi import Depends, Request
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.routing import BaseRoute

from portalab.core.authz_port import ANONYMOUS, Authorizer, Principal, ResourceRef
from portalab.core.errors import Forbidden, NotFound, Unauthorized

PUBLIC_MARKER = "__portalab_public__"

_request_memo: ContextVar[dict[Any, Any] | None] = ContextVar("portalab_authz_memo", default=None)


@contextmanager
def authorization_scope() -> Iterator[dict[Any, Any]]:
    """Per-request memo for the authorization engine (no cross-request cache, spec 003 R6)."""
    memo: dict[Any, Any] = {}
    token = _request_memo.set(memo)
    try:
        yield memo
    finally:
        _request_memo.reset(token)


def request_memo() -> dict[Any, Any] | None:
    """The memo of the current request, or ``None`` outside a request (jobs, CLI)."""
    return _request_memo.get()


class PrincipalResolver(Protocol):
    async def resolve(self, request: Request) -> Principal: ...


class AnonymousResolver:
    """Every caller is anonymous (used when no authentication module is wired)."""

    async def resolve(self, request: Request) -> Principal:
        return ANONYMOUS


def public[F: Callable[..., Any]](endpoint: F) -> F:
    """Mark an endpoint as intentionally reachable without authorization (health, sign-in)."""
    setattr(endpoint, PUBLIC_MARKER, True)
    return endpoint


class RequirePermission:
    """FastAPI dependency: the caller must hold ``permission`` (optionally on a resource)."""

    def __init__(
        self,
        permission: str,
        resource: Callable[[Request], ResourceRef | None] | None = None,
        *,
        hide_existence: bool = False,
    ) -> None:
        self.permission = permission
        self._resource = resource
        self.hide_existence = hide_existence

    async def __call__(self, request: Request) -> Principal:
        principal = await current_principal(request)
        if not principal.is_authenticated:
            raise Unauthorized()
        resource = self._resource(request) if self._resource else None
        authorizer: Authorizer = request.app.state.authorizer
        if await authorizer.is_allowed(principal, self.permission, resource):
            return principal
        if self.hide_existence:
            raise NotFound()  # where existence itself is sensitive (CANONICAL_DECISIONS OQ-19)
        raise Forbidden()


def require(
    permission: str,
    resource: Callable[[Request], ResourceRef | None] | None = None,
    *,
    hide_existence: bool = False,
) -> Any:
    """``Depends(...)`` declaring the permission a route needs.

    Ordering rule: authorize first, then filter by visibility (spec 021) — ``require()`` never reads or
    changes privacy preferences.
    """
    return Depends(RequirePermission(permission, resource, hide_existence=hide_existence))


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


def api_routes(routes: Iterable[BaseRoute]) -> list[APIRoute]:
    """Every API route of an application, including those of included routers (FastAPI nests them)."""
    return [
        context.original_route
        for context in iter_route_contexts(list(routes))
        if isinstance(context.original_route, APIRoute)
    ]
