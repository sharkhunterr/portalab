"""Default-deny enforcement at the composition root (CD-002).

The route-level dependencies (:func:`require`, :func:`public`, …) live in :mod:`portalab.core.authorization`
so modules can use them; this module adds the app-wide :func:`enforce_default_deny` guard that refuses any
route declaring neither, and re-exports the dependencies for the composition root.
"""

import asyncio
import hashlib
import json
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import Request
from fastapi.routing import APIRoute

from portalab.app.intrusion import IntrusionGuard, weigh
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


class SecurityBlocked(Forbidden):
    default_code = "security.blocked"
    default_title = "Blocked after suspicious requests"


async def enforce_default_deny(request: Request) -> None:
    """App-wide dependency: refuse any route that declares neither ``public`` nor a permission — and
    (issue 1) every request of a member whose account the intrusion guard blocked."""
    guard: IntrusionGuard | None = request.app.state._state.get("intrusion_guard")
    if guard is not None and guard.any_user_blocked() and SESSION_COOKIE_NAME in request.cookies:
        principal = await current_principal(request)
        if principal.user_id is not None and guard.user_blocked(str(principal.user_id)) is not None:
            raise SecurityBlocked("Your account is blocked for a while after suspicious requests.")
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
        # 027 (#11): www.gstatic.com serves the Cast SDK (the player's Chromecast button)
        b"default-src 'self'; script-src 'self' https://www.gstatic.com; style-src 'self'; "
        b"img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; media-src 'self' blob:; "
        b"object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
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
_ALERTS: set["asyncio.Task[None]"] = set()  # alerts on their way (kept until done)


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
        guard: IntrusionGuard | None = None,
    ) -> None:
        self.app = app
        self.guard = guard  # issue 1: who probes what they may not reach is blocked
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
        client = scope.get("client") or ("unknown", 0)
        keys = [f"ip:{client[0]}"]
        if (session_hash := _session_key(scope)) is not None:
            keys.append(f"session:{session_hash}")
        if self.guard is not None and path.startswith("/api/"):
            # a signed-in member answers for their own session (and account, checked once they are known);
            # an address is held against requests without one — the members sharing it are never shut out
            left = self.guard.blocked(
                [k for k in keys if k.startswith("session:")] if len(keys) > 1 else keys
            )
            if left is not None:
                retry = str(max(1, int(left + 0.999))).encode()
                await _problem(
                    send,
                    403,
                    "security.blocked",
                    "Blocked after suspicious requests",
                    [(b"retry-after", retry)],
                )
                return
        if path.startswith("/api/") and not exempt:
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
        status = 0

        async def secured_send(message: Message) -> None:
            nonlocal started, status
            if message["type"] == "http.response.start":
                started = True
                status = int(message.get("status", 0))
                existing = {name.lower() for name, _ in message.get("headers", [])}
                message["headers"] = [
                    *message.get("headers", []),
                    *((name, value) for name, value in SECURITY_HEADERS if name not in existing),
                ]
            await send(message)

        await self.app(scope, limited_receive, secured_send)
        if too_large and not started:
            await _problem(send, 413, "request.too_large", "Request body too large", [])
        if self.guard is not None and path.startswith("/api/"):
            raw = scope.get("raw_path") or path.encode()
            query = (scope.get("query_string") or b"").decode("latin-1")
            verdict = weigh(raw.decode("latin-1"), query, status)
            if verdict is not None:
                for block in self.guard.strike(keys, verdict[0], verdict[1], raw.decode("latin-1")):
                    app_state = getattr(scope.get("app"), "state", None)
                    alert = app_state._state.get("security_alert") if app_state is not None else None
                    if alert is not None:
                        task = asyncio.create_task(alert({**block.__dict__, "keys": keys}))
                        _ALERTS.add(task)
                        task.add_done_callback(_ALERTS.discard)
