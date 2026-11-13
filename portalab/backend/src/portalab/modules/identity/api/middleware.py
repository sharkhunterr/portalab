"""Session authentication → :class:`Principal` (``identity.principal``, T024) and cookie helpers.

* the session cookie is ``__Host-`` prefixed, HttpOnly, Secure, SameSite=Lax (research R1) — #395: on a
  portal reached in plain HTTP from a local network, where a browser drops any ``Secure`` cookie, the same
  cookies go without the prefix and without ``Secure`` (a portal set up on a home server, no TLS yet);
* unsafe methods on a cookie-authenticated request require ``X-CSRF-Token`` equal to the token derived from
  the session (double submit bound to the session, R6) — otherwise 403 ``auth.csrf_failed``;
* only Active accounts get a principal; an unknown, expired or revoked cookie is anonymous;
* the database being unreachable fails **closed** with 503, never open (plan §9).
"""

import ipaddress
from datetime import datetime

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from portalab.core.authz_port import ANONYMOUS, Principal
from portalab.core.errors import Forbidden, Unavailable
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import User
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.sessions import IssuedSession, csrf_matches
from portalab.modules.identity.services.visits import record_visit

SESSION_COOKIE = "__Host-portalab_session"
CSRF_COOKIE = "__Host-portalab_csrf"
PLAIN_SESSION_COOKIE = "portalab_session"  # #395: plain HTTP from a local network
PLAIN_CSRF_COOKIE = "portalab_csrf"
LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in ("127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CsrfFailed(Forbidden):
    default_code = "auth.csrf_failed"
    default_title = "Missing or invalid CSRF token"


def identity_module(request: Request) -> IdentityModule:
    module = getattr(request.app.state, "identity_module", None)
    if not isinstance(module, IdentityModule):
        raise Unavailable("Authentication is not available.", code="auth.unavailable")
    return module


def plain_http(request: Request) -> bool:
    """#395: reached in plain HTTP (as the server, or a trusted proxy, sees it) from a local network — never
    through a proxy that is not trusted (#273: its local address would vouch for anyone)."""
    if request.url.scheme != "http" or request.client is None:
        return False
    hops = [hop.strip() for hop in request.headers.get("x-forwarded-for", "").split(",") if hop.strip()]
    if hops and request.client.host not in hops:
        return False  # a proxy the server does not trust brought it
    try:
        address = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    return any(address in network for network in LOCAL_NETWORKS)


def session_token(request: Request) -> str | None:
    """The session cookie this browser sent. The plain one counts only on a plain-HTTP local request: over
    HTTPS a cookie without the ``__Host-`` prefix may have been planted (a sibling subdomain, a network
    attacker) to sign the visitor into someone else's session."""
    token = request.cookies.get(SESSION_COOKIE)
    if token is None and plain_http(request):
        token = request.cookies.get(PLAIN_SESSION_COOKIE)
    return token


def check_csrf(request: Request, token: str) -> None:
    if request.method not in SAFE_METHODS and not csrf_matches(token, request.headers.get(CSRF_HEADER)):
        raise CsrfFailed("This request needs a valid X-CSRF-Token header.")


class SessionPrincipalResolver:
    async def resolve(self, request: Request) -> Principal:
        token = session_token(request)
        if not token:
            return ANONYMOUS
        module = identity_module(request)
        ctx = module.ctx
        try:
            async with ctx.database.unit_of_work() as uow:
                now, seen = ctx.now(), list[datetime]()
                row = await module.sessions.resolve(uow.session, token, now, seen=seen)
                state = None
                if row is not None:
                    state = await uow.session.scalar(select(User.state).where(User.id == row.user_id))
                if row is not None and seen and state == AccountState.ACTIVE.value:
                    await record_visit(ctx, uow.session, row.user_id, now, since=seen[0])
        except (SQLAlchemyError, OSError) as exc:
            raise Unavailable("Authentication is temporarily unavailable.", code="auth.unavailable") from exc
        if row is None or state != AccountState.ACTIVE.value:
            return ANONYMOUS
        check_csrf(request, token)
        return Principal(user_id=row.user_id, session_id=row.id)


def set_session_cookies(response: Response, issued: IssuedSession, max_age: int, request: Request) -> None:
    plain = plain_http(request)
    session, csrf = (PLAIN_SESSION_COOKIE, PLAIN_CSRF_COOKIE) if plain else (SESSION_COOKIE, CSRF_COOKIE)
    response.set_cookie(
        session, issued.token, max_age=max_age, path="/", secure=not plain, httponly=True, samesite="lax"
    )
    response.set_cookie(
        csrf, issued.csrf_token, max_age=max_age, path="/", secure=not plain, httponly=False, samesite="lax"
    )


def clear_session_cookies(response: Response) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=True, httponly=name == SESSION_COOKIE, samesite="lax")
    for name in (PLAIN_SESSION_COOKIE, PLAIN_CSRF_COOKIE):
        response.delete_cookie(name, path="/", httponly=name == PLAIN_SESSION_COOKIE, samesite="lax")
