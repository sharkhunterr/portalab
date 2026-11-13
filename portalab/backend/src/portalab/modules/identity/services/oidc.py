"""Single sign-on (027, OIDC — Authentik): a member signs in with their homelab account.

``start`` sends the browser to the provider (authorization code with PKCE; the state, nonce and verifier are
kept a few minutes, used once). ``finish`` exchanges the code, checks the ID token — its signature against
the provider's published keys, issuer, audience, expiry and nonce — then finds the member: the provider
account already linked, else the portal account with the same verified e-mail (linked then), else — when the
administrators allow it — a new portal account. The session is opened like a password sign-in (the account's
state rules apply)."""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

import httpx
import jwt
from sqlalchemy import delete, func, select

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.core import egress
from portalab.core.errors import Unauthorized, Unavailable
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import ExternalIdentity, OidcLogin, User
from portalab.modules.identity.observability import log
from portalab.modules.identity.services.account_service import AccountService, LoginTaken
from portalab.modules.identity.services.auth import AuthService, SignedIn
from portalab.modules.identity.services.common import SYSTEM, DisplayNameTaken, publish
from portalab.modules.identity.settings import (
    OIDC_CLIENT_ID,
    OIDC_CLIENT_SECRET,
    OIDC_CREATE,
    OIDC_ENABLED,
    OIDC_ISSUER,
    OIDC_LABEL,
    OIDC_TRUST_EMAIL,
)

PENDING = timedelta(minutes=10)
TIMEOUT = 10.0


@dataclass(frozen=True, slots=True)
class OidcSettings:
    enabled: bool
    issuer: str
    client_id: str
    client_secret: str
    label: str
    create_accounts: bool
    trust_unverified_email: bool = False  # issue 403: an e-mail the provider does not vouch for links nobody

    @property
    def ready(self) -> bool:
        return self.enabled and bool(self.issuer and self.client_id and self.client_secret)


class SignOnFailed(Unauthorized):
    def __init__(self, reason: str) -> None:
        super().__init__("The single sign-on did not succeed.", code="auth.sso_failed")
        self.reason = reason


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def browser_binding(state: str) -> str:
    """#277: what the browser that started a sign-on keeps (a cookie) — the way back is accepted only in that
    browser, so nobody can finish someone else's sign-on (or their own in a victim's browser)."""
    return hashlib.sha256(state[:64].encode()).hexdigest()


def state_of(provider_url: str) -> str:
    return parse_qs(urlsplit(provider_url).query)["state"][0]


def safe_next(path: str | None) -> str:
    """Only a route of the portal itself (never another site)."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path[:512]


class OidcService:
    def __init__(self, ctx: IdentityContext, auth: AuthService, accounts: AccountService) -> None:
        self.ctx = ctx
        self.auth = auth
        self.accounts = accounts
        self._discovery: dict[str, Mapping[str, Any]] = {}
        self.transport: httpx.AsyncBaseTransport | None = None  # tests talk to a fake provider

    async def settings(self) -> OidcSettings:
        values: dict[str, Any] = {}
        try:
            providers = self.ctx.capabilities.system_providers(CONFIG)
            reader = providers[0].provider if providers else None
        except Exception:
            reader = None
        keys = (
            OIDC_ENABLED,
            OIDC_ISSUER,
            OIDC_CLIENT_ID,
            OIDC_CLIENT_SECRET,
            OIDC_LABEL,
            OIDC_CREATE,
            OIDC_TRUST_EMAIL,
        )
        for key in keys:
            try:
                values[key] = (await reader.get(key)).value if reader is not None else None
            except Exception:
                values[key] = None
        return OidcSettings(
            enabled=bool(values[OIDC_ENABLED]),
            issuer=str(values[OIDC_ISSUER] or "").rstrip("/"),
            client_id=str(values[OIDC_CLIENT_ID] or ""),
            client_secret=str(values[OIDC_CLIENT_SECRET] or ""),
            label=str(values[OIDC_LABEL] or "Authentik")[:60],
            create_accounts=values[OIDC_CREATE] is not False,
            trust_unverified_email=values[OIDC_TRUST_EMAIL] is True,
        )

    async def _metadata(self, issuer: str) -> Mapping[str, Any]:
        if issuer not in self._discovery:
            egress.EGRESS.allow(urlsplit(issuer).hostname, "sign-in")  # the configured provider
            async with httpx.AsyncClient(
                timeout=TIMEOUT, transport=self.transport, event_hooks=egress.hooks()
            ) as client:
                answer = await client.get(f"{issuer}/.well-known/openid-configuration")
                answer.raise_for_status()
                metadata = answer.json()
            if not isinstance(metadata, Mapping) or "authorization_endpoint" not in metadata:
                raise Unavailable(
                    "The single sign-on provider cannot be reached.", code="auth.sso_unavailable"
                )
            # issue 403: the provider answering is the one configured (OpenID Connect Discovery §4.3)
            if str(metadata.get("issuer") or "").rstrip("/") != issuer.rstrip("/"):
                raise Unavailable(
                    "The single sign-on provider names another issuer.", code="auth.sso_unavailable"
                )
            self._discovery[issuer] = metadata
        return self._discovery[issuer]

    async def start(self, redirect_uri: str, next_path: str | None) -> str:
        """The provider's address to send the browser to."""
        config = await self.settings()
        if not config.ready:
            raise Unavailable("The single sign-on is not set up.", code="auth.sso_disabled")
        metadata = await self._metadata(config.issuer)
        state, nonce, verifier = (
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(64),
        )
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await uow.session.execute(delete(OidcLogin).where(OidcLogin.created_at < now - PENDING))
            uow.session.add(
                OidcLogin(
                    state=state[:64],
                    nonce=nonce[:64],
                    verifier=verifier[:128],
                    next_path=safe_next(next_path),
                    created_at=now,
                )
            )
        challenge = _b64(hashlib.sha256(verifier[:128].encode()).digest())
        query = urlencode(
            {
                "response_type": "code",
                "client_id": config.client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid email profile",
                "state": state[:64],
                "nonce": nonce[:64],
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{metadata['authorization_endpoint']}?{query}"

    async def _claims(
        self, config: OidcSettings, code: str, redirect_uri: str, login: OidcLogin
    ) -> dict[str, Any]:
        metadata = await self._metadata(config.issuer)
        egress.EGRESS.allow(urlsplit(str(metadata["token_endpoint"])).hostname, "sign-in")
        async with httpx.AsyncClient(
            timeout=TIMEOUT, transport=self.transport, event_hooks=egress.hooks()
        ) as client:
            answer = await client.post(
                str(metadata["token_endpoint"]),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": login.verifier,
                },
                auth=(config.client_id, config.client_secret),
            )
            if answer.status_code != 200:
                raise SignOnFailed(f"token endpoint answered {answer.status_code}")
            tokens = answer.json()
            keys = (await client.get(str(metadata["jwks_uri"]))).json()
        raw = tokens.get("id_token") if isinstance(tokens, Mapping) else None
        if not isinstance(raw, str):
            raise SignOnFailed("no ID token")
        header = jwt.get_unverified_header(raw)
        candidates = [
            k for k in keys.get("keys", []) if not header.get("kid") or k.get("kid") == header.get("kid")
        ]
        if not candidates:
            raise SignOnFailed("unknown signing key")
        key = jwt.PyJWK(candidates[0])
        try:
            claims = jwt.decode(
                raw,
                key.key,
                algorithms=[header.get("alg", "RS256")]
                if header.get("alg") in ("RS256", "ES256", "PS256")
                else ["RS256"],
                audience=config.client_id,
                issuer=str(metadata.get("issuer") or config.issuer),
                options={"require": ["exp", "iat", "sub"]},
                leeway=60,
            )
        except jwt.PyJWTError as exc:
            raise SignOnFailed(type(exc).__name__) from exc
        if claims.get("nonce") != login.nonce:
            raise SignOnFailed("nonce mismatch")
        return dict(claims)

    async def finish(
        self,
        code: str,
        state: str,
        redirect_uri: str,
        *,
        client_ip: str | None,
        user_agent: str | None,
        previous_token: str | None,
        browser: str | None,
    ) -> tuple[SignedIn, str]:
        """Check the provider's answer and open the member's session; returns it with where to go next.
        ``browser`` is what the browser kept when it started (:func:`browser_binding`)."""
        config = await self.settings()
        if not config.ready:
            raise Unavailable("The single sign-on is not set up.", code="auth.sso_disabled")
        if not browser or not hmac.compare_digest(browser, browser_binding(state)):
            raise SignOnFailed("started in another browser")
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            login = await uow.session.get(OidcLogin, state[:64], with_for_update=True)
            if login is not None:
                await uow.session.delete(login)  # used once
        if login is None or login.created_at < now - PENDING:
            raise SignOnFailed("unknown or expired state")
        claims = await self._claims(config, code, redirect_uri, login)
        user_id = await self._member(config, claims, await self._signed_in(previous_token))
        signed = await self.auth.open_session(
            user_id, client_ip=client_ip, user_agent=user_agent, previous_token=previous_token, method="sso"
        )
        return signed, login.next_path

    async def _signed_in(self, token: str | None) -> UUID | None:
        """The member already signed in in this browser (a live session), if any."""
        if not token:
            return None
        async with self.ctx.database.unit_of_work() as uow:
            row = await self.auth.sessions.resolve(uow.session, token, self.ctx.now())
            return row.user_id if row is not None else None

    async def _member(self, config: OidcSettings, claims: Mapping[str, Any], signed_in: UUID | None) -> UUID:
        """The member a provider account signs in as: the one it is linked to; else the member signed in in
        this browser; else the member of the same e-mail (linked by the server, nobody does it by hand) —
        the Admin only when the provider **vouches** for that e-mail (#277: anyone able to set their e-mail
        at the provider would otherwise become the Admin); else a new member, when allowed."""
        issuer, subject = config.issuer, str(claims["sub"])[:255]
        email = str(claims.get("email") or "").strip().lower() or None
        vouched = claims.get("email_verified") is True
        # issue 403: an e-mail the provider leaves unsaid (Authentik's own users) links an account only when
        # the administrator trusts the provider's e-mails; one it disowns, never
        trusted = vouched or (config.trust_unverified_email and claims.get("email_verified") is not False)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            session = uow.session
            linked = await session.scalar(
                select(ExternalIdentity).where(
                    ExternalIdentity.issuer == issuer, ExternalIdentity.subject == subject
                )
            )
            if linked is not None:
                linked.last_sign_in_at = now
                return linked.user_id
            user = await session.get(User, signed_in) if signed_in is not None else None
            if user is None and email and claims.get("email_verified") is not False:
                user = await session.scalar(select(User).where(func.lower(User.email) == email))
                if user is not None and not trusted:
                    # neither linked (anyone could set that e-mail at the provider) nor duplicated
                    raise SignOnFailed("the provider does not vouch for this e-mail")
                if (
                    user is not None
                    and not vouched
                    and await self.ctx.admin_authority().is_admin(session, user.id)
                ):
                    raise SignOnFailed("the provider does not vouch for the Admin's e-mail")
            if user is None:
                if not config.create_accounts:
                    raise SignOnFailed("no portal account for this provider account")
                login_name = str(claims.get("preferred_username") or (email or "").split("@")[0] or subject)
                name = str(claims.get("name") or login_name)
                user = None
                for attempt in range(3):  # a login or a name already taken: made unique
                    suffix = "" if attempt == 0 else f"-{subject[: 4 * attempt]}"
                    try:
                        async with session.begin_nested():
                            user = await self.accounts.create_user(
                                session,
                                login=f"{login_name[: 64 - len(suffix)]}{suffix}",
                                display_name=f"{name[: 64 - len(suffix)]}{suffix}",
                                email=email,
                                state=AccountState.ACTIVE,
                                actor=SYSTEM,
                                reason="single_sign_on",
                            )
                        break
                    except (LoginTaken, DisplayNameTaken):
                        continue
                if user is None:
                    raise SignOnFailed("no free login for this provider account")
                log.info("account created from the single sign-on")
            session.add(
                ExternalIdentity(
                    user_id=user.id, issuer=issuer, subject=subject, created_at=now, last_sign_in_at=now
                )
            )
            # issue 407: the member hears that a provider account now signs in as them
            await publish(
                self.ctx, session, "user.sso_linked", user.id, actor=None, occurred_at=now,
                metadata={"provider": urlsplit(issuer).hostname or issuer},
                dedup_key=f"sso_linked:{user.id}:{subject}",
            )  # fmt: skip
            return user.id
