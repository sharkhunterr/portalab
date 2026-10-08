"""Default-deny enforcement at the composition root (CD-002).

The route-level dependencies (:func:`require`, :func:`public`, …) live in :mod:`portalab.core.authorization`
so modules can use them; this module adds the app-wide :func:`enforce_default_deny` guard that refuses any
route declaring neither, and re-exports the dependencies for the composition root.
"""

import hashlib
import json
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

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
from portalab.core.errors import PROBLEM_CONTENT_TYPE, Forbidden, Unauthorized

__all__ = [
    "PUBLIC_MARKER",
    "AnonymousResolver",
    "PrincipalResolver",
    "RequirePermission",
    "api_routes",
    "current_principal",
    "enforce_default_deny",
    "enforce_terms",
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


class TermsNotAccepted(Forbidden):
    default_code = "terms.acceptance_required"
    default_title = "The terms of use must be accepted"


# What a member may still do before accepting the terms in force (027): sign in or out, read and accept the
# terms, load the portal's look and words, and exercise their rights on their own data (export, deletion).
TERMS_OPEN_PATHS = frozenset({"/api/v1/me", "/api/v1/me/preferences", "/api/v1/terms"})
TERMS_OPEN_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/me/terms",
    "/api/v1/me/privacy",
    "/api/v1/me/export",
    "/api/v1/me/deletion",
    "/api/v1/ui/",
    "/api/v1/i18n/",
)


async def enforce_terms(request: Request) -> None:
    """App-wide dependency (027): a signed-in member who has not accepted the terms in force cannot use the
    portal — every protected route answers ``terms.acceptance_required`` until they do."""
    route = request.scope.get("route")
    if not isinstance(route, APIRoute) or route_access(route) in (None, "public"):
        return
    path = request.url.path
    if path in TERMS_OPEN_PATHS or path.startswith(TERMS_OPEN_PREFIXES):
        return
    terms = getattr(getattr(request.app.state, "privacy_module", None), "terms", None)
    if terms is None:
        return
    try:
        principal = await current_principal(request)
    except Exception:
        return  # the route's own permission check answers
    if principal.user_id is None or principal.channel != "user" or principal.acting_for is not None:
        return
    if await terms.must_accept(principal.user_id):
        raise TermsNotAccepted("Accept the terms of use to continue.")


# --- security hardening baseline (spec 021 T033, research R10) ------------------------------------------

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
        b"font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; "
        b"frame-ancestors 'none'",
    ),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
)
EXEMPT_PATHS = frozenset({"/healthz", "/readyz"})
# Read-only, cacheable documents the SPA fetches by the dozen on every full load (one catalog per i18n
# namespace): counting them would rate-limit a member who simply reloads a few pages (027).
EXEMPT_GET_PREFIXES = ("/api/v1/i18n/catalogs/",)
SESSION_COOKIE_NAME = "__Host-portalab_session"


class SlidingWindowLimiter:
    """In-process limiter (single node, plan risk R4): at most ``limit`` hits per key per ``window``."""

    def __init__(self, limit: int, window: float = 60.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> float | None:
        """Record a hit; returns ``None`` when allowed, else the seconds to wait."""
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(0.0, hits[0] + self.window - now)
            hits.append(now)
            if len(self._hits) > 50_000:  # bound memory under address churn
                for stale in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
                    del self._hits[stale]
            return None


def _session_key(scope: Scope) -> str | None:
    for name, value in scope.get("headers", ()):
        if name == b"cookie":
            for part in value.decode("latin-1").split(";"):
                key, _, token = part.strip().partition("=")
                if key == SESSION_COOKIE_NAME and token:
                    return hashlib.sha256(token.encode()).hexdigest()
    return None


async def _problem(
    send: Send, status: int, code: str, title: str, extra_headers: list[tuple[bytes, bytes]]
) -> None:
    body = json.dumps(
        {"type": f"https://portalab.dev/problems/{code}", "title": title, "status": status, "code": code}
    )
    headers = [(b"content-type", PROBLEM_CONTENT_TYPE.encode()), *extra_headers, *SECURITY_HEADERS]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body.encode()})


class SecurityMiddleware:
    """Security headers on every response, request-body cap (413) and rate limits per IP and per session
    (429) on the API; health probes and static assets (the SPA's chunks, fonts, sounds — dozens per page
    load) are exempt from rate limiting."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int,
        per_ip_per_minute: int,
        per_user_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.per_ip = SlidingWindowLimiter(per_ip_per_minute, clock=clock)
        self.per_user = SlidingWindowLimiter(per_user_per_minute, clock=clock)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        exempt = path in EXEMPT_PATHS or (
            scope.get("method") == "GET" and path.startswith(EXEMPT_GET_PREFIXES)
        )
        if path.startswith("/api/") and not exempt:
            client = scope.get("client") or ("unknown", 0)
            wait = self.per_ip.hit(f"ip:{client[0]}")
            session = _session_key(scope)
            if wait is None and session is not None:
                wait = self.per_user.hit(f"session:{session}")
            if wait is not None:
                retry = str(max(1, int(wait + 0.999))).encode()
                await _problem(send, 429, "rate_limited", "Too many requests", [(b"retry-after", retry)])
                return
        declared = next(
            (value for name, value in scope.get("headers", ()) if name == b"content-length"), None
        )
        if declared is not None and declared.isdigit() and int(declared) > self.max_body_bytes:
            await _problem(send, 413, "request.too_large", "Request body too large", [])
            return

        received = 0
        too_large = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    too_large = True
                    return {"type": "http.disconnect"}
            return message

        started = False

        async def secured_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                existing = {name.lower() for name, _ in message.get("headers", [])}
                message["headers"] = [
                    *message.get("headers", []),
                    *((name, value) for name, value in SECURITY_HEADERS if name not in existing),
                ]
            await send(message)

        await self.app(scope, limited_receive, secured_send)
        if too_large and not started:
            await _problem(send, 413, "request.too_large", "Request body too large", [])
