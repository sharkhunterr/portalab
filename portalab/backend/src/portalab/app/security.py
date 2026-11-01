"""Default-deny enforcement at the composition root (CD-002).

The route-level dependencies (:func:`require`, :func:`public`, …) live in :mod:`portalab.core.authorization`
so modules can use them; this module adds the app-wide :func:`enforce_default_deny` guard that refuses any
route declaring neither, and re-exports the dependencies for the composition root.
"""

import asyncio
import hashlib
import ipaddress
import json
import re
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable, Iterable, MutableMapping
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.routing import APIRoute
from starlette.requests import Request as StarletteRequest

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
from portalab.core.logging import get_logger
from portalab.modules.identity.guard import IntrusionGuard, weigh

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
        # 027 (#11): www.gstatic.com serves the Cast SDK (the player's Chromecast button) — #280: its three
        # folders only (the loader, the framework, Android's sender), not every script Google hosts there
        b"default-src 'self'; script-src 'self' https://www.gstatic.com/cv/js/sender/ "
        b"https://www.gstatic.com/cast/sdk/libs/ https://www.gstatic.com/eureka/clank/; style-src 'self'; "
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
# 028: and the files of the live visual packs (immutable, fingerprinted, a page shows dozens of them)
EXEMPT_GET_PREFIXES = ("/api/v1/i18n/catalogs/", "/api/v1/visuals/files/", "/api/v1/visuals/bundle/")
# #305: the pictures a page shows (posters, backdrops, portraits, avatars) — dozens on a title's page: they
# count on a budget of their own, four times the member's, so a page rich in pictures never spends the
# budget of the calls that matter (a reload's session check answering « too many requests »)
IMAGE_GET_PREFIXES = (
    "/api/v1/media/metadata-images",
    "/api/v1/media/images/",
    "/api/v1/media/person/portrait",
)
IMAGE_GET = re.compile(r"^/api/v1/users/[^/]+/avatar$")
IMAGE_BUDGET = 4
SESSION_COOKIE_NAME = "__Host-portalab_session"
log = get_logger("portalab.security")
_ALERTS: set["asyncio.Task[None]"] = set()  # alerts on their way (kept until done)

# --- the minimal public surface (spec 028 FR-036/FR-037, issue 135) -----------------------------------------
# Without a session, only these answer: signing in and out, the single sign-on, the single-purpose links sent
# by e-mail or to a device, the words of the sign-in page — and the first run while nobody has set the portal
# up (its route answers nothing once it has). Every other address, existing or not, gets the very same answer.
ANONYMOUS_PATHS = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/oidc",
        "/api/v1/auth/oidc/start",
        "/api/v1/auth/oidc/callback",
        "/api/v1/auth/register",
        "/api/v1/auth/verify",
        "/api/v1/auth/deletion/cancel",
        "/api/v1/admin/first-run",
        # issue 247: a new portal's arrival wizard brings a backup in (answered only until it is set up)
        "/api/v1/admin/first-run/import",
        "/api/v1/admin/first-run/import/upload",
        "/api/v1/admin/first-run/import/inspect",
        "/api/v1/admin/first-run/import/status",
        # issue 159: the site's name, slogan, images and home-screen manifest — the sign-in page shows them
        "/api/v1/auth/site",
        "/api/v1/auth/site/logo",
        "/api/v1/auth/site/icon",
        "/api/v1/auth/site/manifest",
        # issue 246: the languages offered before signing in (the arrival wizard, sign-in)
        "/api/v1/i18n/public/languages",
    }
)
# #275: setting a portal up (or bringing a backup into it) without an account — only from the local networks
SETUP_PATHS = frozenset(p for p in ANONYMOUS_PATHS if p.startswith("/api/v1/admin/first-run"))
# #276: where passwords and accounts are tried — held to their own pace per address, and an address blocked
# stays blocked there whatever session cookie it shows
SIGN_IN_PATHS = (
    frozenset({"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/verify"}) | SETUP_PATHS
)
ANONYMOUS_PREFIXES = ("/api/v1/media/remote/",)  # a casting device's stream, by its ticket
# issue 157: the terms of use, on the sign-in page — only while the administrators offer them there
SIGN_IN_TERMS_PATH = "/api/v1/auth/terms"
ANONYMOUS_CATALOGS = frozenset({"auth", "common", "errors"})  # the sign-in page's words
PUBLIC_CATALOGS = frozenset({"core", "account"})
# issue 247: a backup's archive (hundreds of MB, GB with its images) sent to a new portal's arrival wizard —
# answered only until the portal is set up
LARGE_BODIES = {
    "/api/v1/admin/first-run/import/upload": 200 * 1024**3
}  # issue 246: the arrival wizard's and sign-in's words
HEALTH_PATHS = frozenset({"/healthz", "/readyz", "/metrics"})
# who may ask the health checks: the machine itself and the local networks (the administrator narrows it)
DEFAULT_HEALTH_NETWORKS = (
    "127.0.0.0/8",
    "::1/128",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "fc00::/7",
)
SIGN_IN_REQUIRED = (401, "unauthorized", "Authentication required")


def anonymous_allowed(path: str) -> bool:
    """Whether a request without a session may reach ``path`` (API addresses; the SPA's pages always load —
    they are the sign-in page — and its static files are gated apart)."""
    if path in ANONYMOUS_PATHS or path.startswith(ANONYMOUS_PREFIXES):
        return True
    if path.startswith("/api/v1/i18n/catalogs/"):
        return path.rsplit("/", 1)[-1] in ANONYMOUS_CATALOGS
    if path.startswith("/api/v1/i18n/public/catalogs/"):  # issue 246: the pre-sign-in screens' words
        return path.rsplit("/", 1)[-1] in PUBLIC_CATALOGS
    return not path.startswith("/api/")


async def _terms_on_sign_in(app_state: Any) -> bool:
    terms = getattr(getattr(app_state, "privacy_module", None), "terms", None) if app_state else None
    if terms is None:
        return False
    try:
        return bool(await terms.on_sign_in())
    except Exception:
        return False  # the database away: the generic answer


def public_assets_of(static_dir: Path | None) -> frozenset[str] | None:
    """The static files of the sign-in page (``public-assets.json``, written by the SPA's build): the only
    ones a visitor may load. ``None`` when the build wrote none (development): every file loads."""
    if static_dir is None:
        return None
    try:
        names = json.loads((static_dir / "public-assets.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return frozenset(str(n) for n in names) if isinstance(names, list) else None


def forwarded_hops(scope: Scope) -> list[str]:
    return [
        hop.strip()
        for name, value in scope.get("headers", ())
        if name == b"x-forwarded-for"
        for hop in value.decode("latin-1").split(",")
        if hop.strip()
    ]


def behind_untrusted_proxy(scope: Scope) -> bool:
    """#273: the request names who it is for (``X-Forwarded-For``) but the server did not believe it — a
    reverse proxy that is not in ``TRUSTED_PROXIES``: the address seen is the proxy's, not the visitor's."""
    hops = forwarded_hops(scope)
    client = (scope.get("client") or ("", 0))[0]
    return bool(hops) and client not in hops


def networks_of(cidrs: Iterable[str]) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return tuple(ipaddress.ip_network(c.strip(), strict=False) for c in cidrs if c.strip())


def address_in(address: str, networks: Iterable[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in networks)


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


def _picture(scope: Scope, path: str) -> bool:
    return scope.get("method") == "GET" and (
        path.startswith(IMAGE_GET_PREFIXES) or bool(IMAGE_GET.match(path))
    )


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
        sign_in_per_minute: int = 30,
        clock: Callable[[], float] = time.monotonic,
        guard: IntrusionGuard | None = None,
        anonymous_gate: bool = False,
        health_networks: Iterable[str] = DEFAULT_HEALTH_NETWORKS,
        setup_networks: Iterable[str] = DEFAULT_HEALTH_NETWORKS,
        public_assets: frozenset[str] | None = None,
    ) -> None:
        self.app = app
        self.guard = guard  # issue 1: who probes what they may not reach is blocked
        self.anonymous_gate = anonymous_gate  # 028: nothing answers a visitor but signing in
        self.health_networks = networks_of(health_networks)
        self.setup_networks = networks_of(setup_networks)
        self._proxy_warned = False
        self.public_assets = public_assets  # 028: the static files the sign-in page needs (None: all)
        self.max_body_bytes = max_body_bytes
        self.per_ip = SlidingWindowLimiter(per_ip_per_minute, clock=clock)
        self.per_user = SlidingWindowLimiter(per_user_per_minute, clock=clock)
        self.images = SlidingWindowLimiter(per_user_per_minute * IMAGE_BUDGET, clock=clock)
        self.sign_in = SlidingWindowLimiter(sign_in_per_minute, clock=clock)

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
                [k for k in keys if k.startswith("session:")]
                if len(keys) > 1 and path not in SIGN_IN_PATHS
                else keys
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
        if path in HEALTH_PATHS and not self._local(scope, self.health_networks):
            await self._refuse_anonymous(scope, send, keys, path)
            return
        if path.startswith("/api/") and not exempt and _picture(scope, path):
            wait = self.images.hit(f"images:{_session_key(scope) or client[0]}")
            if wait is not None:
                retry = str(max(1, int(wait + 0.999))).encode()
                await _problem(send, 429, "rate_limited", "Too many requests", [(b"retry-after", retry)])
                return
        elif path.startswith("/api/") and not exempt:
            wait = self.per_ip.hit(f"ip:{client[0]}")
            if wait is None and path in SIGN_IN_PATHS and scope.get("method") == "POST":
                wait = self.sign_in.hit(f"ip:{client[0]}")
            session = _session_key(scope)
            if wait is None and session is not None:
                wait = self.per_user.hit(f"session:{session}")
            if wait is not None:
                retry = str(max(1, int(wait + 0.999))).encode()
                await _problem(send, 429, "rate_limited", "Too many requests", [(b"retry-after", retry)])
                return
        if self.anonymous_gate and not await self._may_pass(scope, path):
            await self._refuse_anonymous(scope, send, keys, path)
            return
        declared = next(
            (value for name, value in scope.get("headers", ()) if name == b"content-length"), None
        )
        cap = LARGE_BODIES.get(path, self.max_body_bytes)
        if declared is not None and declared.isdigit() and int(declared) > cap:
            await _problem(send, 413, "request.too_large", "Request body too large", [])
            return

        received = 0
        too_large = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > cap:
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
        self._weigh(scope, keys, path, status)

    def _local(self, scope: Scope, networks: Iterable[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
        """Whether the request comes from one of ``networks`` — never when a proxy that is not trusted
        brought it (#273: its own local address would vouch for anyone on the internet)."""
        if behind_untrusted_proxy(scope):
            if not self._proxy_warned:
                self._proxy_warned = True
                log.warning(
                    "requests arrive through a reverse proxy that is not trusted: set TRUSTED_PROXIES to its "
                    "address, or every visitor shares the proxy's address (rate limits, blocking, audit)",
                    extra={"fields": {"proxy": (scope.get("client") or ("?", 0))[0]}},
                )
            return False
        return address_in(str((scope.get("client") or ("", 0))[0]), networks)

    async def _may_pass(self, scope: Scope, path: str) -> bool:
        """028: a request without a valid session reaches only the public surface."""
        if path.startswith("/assets/") and self.public_assets is not None:
            # the SPA's chunks: those of the sign-in page for everyone, the rest once signed in (by its
            # cookie: code, no data — checking the session for dozens of files would cost more than it saves)
            return path.rsplit("/", 1)[-1] in self.public_assets or _session_key(scope) is not None
        if anonymous_allowed(path) and (path not in SETUP_PATHS or self._local(scope, self.setup_networks)):
            return True
        app_state = getattr(scope.get("app"), "state", None)
        if path == SIGN_IN_TERMS_PATH and await _terms_on_sign_in(app_state):
            return True
        if app_state is None or app_state._state.get("principal_resolver") is None:
            return True  # no identity wired (tests of a bare app): the routes answer for themselves
        try:
            principal = await current_principal(StarletteRequest(scope))  # cached for the routes after it
        except Exception:
            return True  # a session that resolves but fails a check (CSRF…): the route answers precisely
        return bool(principal.is_authenticated)

    async def _refuse_anonymous(self, scope: Scope, send: Send, keys: list[str], path: str) -> None:
        status, code, title = SIGN_IN_REQUIRED
        await _problem(send, status, code, title, [])
        self._weigh(scope, keys, path, status)

    def _weigh(self, scope: Scope, keys: list[str], path: str, status: int) -> None:
        if self.guard is None or not path.startswith("/api/"):
            return
        raw = scope.get("raw_path") or path.encode()
        query = (scope.get("query_string") or b"").decode("latin-1")
        verdict = weigh(raw.decode("latin-1"), query, status)
        if verdict is None:
            return
        for block in self.guard.strike(keys, verdict[0], verdict[1], raw.decode("latin-1")):
            app_state = getattr(scope.get("app"), "state", None)
            alert = app_state._state.get("security_alert") if app_state is not None else None
            if alert is not None:
                task = asyncio.create_task(alert({**block.__dict__, "keys": keys}))
                _ALERTS.add(task)
                task.add_done_callback(_ALERTS.discard)
