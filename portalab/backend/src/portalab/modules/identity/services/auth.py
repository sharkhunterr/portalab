"""Authentication: ``AuthProvider`` port, local provider, sign-in/sign-out orchestration (T020-T023).

Non-enumeration (research R4, SC-002): unknown login, wrong password and *any* account state answer the
same ``auth.invalid_credentials`` after the same Argon2 work. Only after valid credentials may the answer
disclose that the account is unavailable (``auth.account_unavailable``). Failed attempts are audited with a
hashed identifier and the client network prefix, never the raw login.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.display_name import login_lookup_key
from portalab.modules.identity.domain.state_machine import SIGN_IN_ALLOWED, AccountState
from portalab.modules.identity.models import Credential, User
from portalab.modules.identity.observability import metrics
from portalab.modules.identity.services.account_service import AccountService
from portalab.modules.identity.services.common import (
    AccountUnavailable,
    InvalidCredentials,
    Throttled,
    audit,
    publish,
    self_actor,
    user_ref,
)
from portalab.modules.identity.services.credentials import CredentialHasher, set_password
from portalab.modules.identity.services.sessions import IssuedSession, SessionService, ip_prefix
from portalab.modules.identity.services.throttle import LoginThrottleService, throttle_key


@dataclass(frozen=True, slots=True)
class AuthResult:
    user_id: UUID


@dataclass(frozen=True, slots=True)
class Denied:
    reason: str = "invalid_credentials"


class AuthProvider(Protocol):
    """Port for authentication methods; OIDC/MFA providers implement it later (research R3)."""

    async def authenticate(self, session: AsyncSession, login: str, password: str) -> AuthResult | Denied: ...


class LocalAuthProvider:
    def __init__(self, hasher: CredentialHasher, ctx: IdentityContext) -> None:
        self.hasher = hasher
        self.ctx = ctx

    async def authenticate(self, session: AsyncSession, login: str, password: str) -> AuthResult | Denied:
        key = login_lookup_key(login)
        row = None
        if key is not None:
            row = (
                await session.execute(
                    select(User.id, Credential.hash)
                    .join(Credential, Credential.user_id == User.id, isouter=True)
                    .where(User.login == key)
                )
            ).one_or_none()
        stored = row.hash if row is not None else None
        if not await self.hasher.verify(stored, password) or row is None or stored is None:
            return Denied()
        if self.hasher.needs_rehash(stored):
            await set_password(session, self.hasher, row.id, password, self.ctx.now())
        return AuthResult(row.id)


@dataclass(frozen=True, slots=True)
class SignedIn:
    user_id: UUID
    display_name: str | None
    issued: IssuedSession


class AuthService:
    def __init__(
        self,
        ctx: IdentityContext,
        provider: AuthProvider,
        sessions: SessionService,
        throttle: LoginThrottleService,
        accounts: AccountService,
    ) -> None:
        self.ctx = ctx
        self.provider = provider
        self.sessions = sessions
        self.throttle = throttle
        self.accounts = accounts

    async def verify_credentials(self, login: str, password: str, *, client_ip: str | None) -> UUID:
        """Throttled credential check shared by sign-in and re-authentication flows."""
        prefix = ip_prefix(client_ip)
        key = throttle_key(login, prefix)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            blocked = await self.throttle.blocked_until(uow.session, key, now)
        if blocked is not None:
            metrics.increment("identity.login.throttled")
            raise Throttled(
                "Too many attempts. Try again later.",
                extensions={"retry_after_seconds": max(1, int((blocked - now).total_seconds()))},
            )
        async with self.ctx.database.unit_of_work() as uow:
            result = await self.provider.authenticate(uow.session, login, password)
            if isinstance(result, AuthResult):
                await self.throttle.clear(uow.session, key)
        if isinstance(result, Denied):
            await self._record_failure(key, prefix, now)
            raise InvalidCredentials()
        return result.user_id

    async def _record_failure(self, key: str, prefix: str | None, now: datetime) -> None:
        metrics.increment("identity.login.failed")
        async with self.ctx.database.unit_of_work() as uow:
            await self.throttle.record_failure(uow.session, key, now)
            await audit(
                self.ctx,
                uow.session,
                "auth.sign_in_failed",
                None,
                decision="deny",
                result="failure",
                context={"identifier_hash": key[:16], "ip_prefix": prefix},
            )

    async def sign_in(
        self,
        login: str,
        password: str,
        *,
        client_ip: str | None,
        user_agent: str | None,
        previous_token: str | None = None,
    ) -> SignedIn:
        user_id = await self.verify_credentials(login, password, client_ip=client_ip)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            user = await self.accounts.get_for_update(uow.session, user_id)
            state = AccountState(user.state)
            if state not in SIGN_IN_ALLOWED:
                unavailable = AccountUnavailable(
                    "This account cannot sign in right now.", extensions=_state_details(user)
                )
            else:
                unavailable = None
                principal = Principal(user_id=user.id)
                if state is AccountState.INACTIVE:
                    await self.accounts.transition(
                        uow.session, user, AccountState.ACTIVE, self_actor(principal), reason="sign_in"
                    )
                if previous_token:  # session fixation: never keep a pre-login session
                    await self._revoke_token(uow.session, previous_token, now, "rotated")
                issued = await self.sessions.create(
                    uow.session, user.id, now, user_agent=user_agent, client_ip=client_ip
                )
                user.last_sign_in_at = now
                await publish(
                    self.ctx,
                    uow.session,
                    "user.signed_in",
                    user.id,
                    actor=Principal(user_id=user.id, session_id=issued.session_id),
                    occurred_at=now,
                    metadata={"session_id": str(issued.session_id)},
                    dedup_key=f"session:{issued.session_id}:signed_in",
                )
                display_name = user.display_name
        if unavailable is not None:
            metrics.increment("identity.login.unavailable")
            raise unavailable
        metrics.increment("identity.login.succeeded")
        return SignedIn(user_id, display_name, issued)

    async def _revoke_token(
        self, session: AsyncSession, token: str, now: datetime, reason: str
    ) -> UUID | None:
        row = await self.sessions.resolve(session, token, now)
        if row is None:
            return None
        await self.sessions.revoke(session, row.id, now, reason)
        return row.user_id

    async def sign_out(self, token: str) -> bool:
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            row = await self.sessions.resolve(uow.session, token, now)
            if row is None:
                return False
            await self.sessions.revoke(uow.session, row.id, now, "logout")
            await publish(
                self.ctx,
                uow.session,
                "user.signed_out",
                row.user_id,
                actor=Principal(user_id=row.user_id, session_id=row.id),
                occurred_at=now,
                metadata={"session_id": str(row.id)},
                dedup_key=f"session:{row.id}:signed_out",
            )
            await audit(
                self.ctx,
                uow.session,
                "user.signed_out",
                Principal(user_id=row.user_id),
                resource=user_ref(row.user_id),
            )
        metrics.increment("identity.sessions.revoked")
        return True

    async def reauthenticate(self, principal: Principal, password: str, *, client_ip: str | None) -> None:
        """Step-up re-authentication of the signed-in user (deletion, Admin transfer)."""
        if principal.user_id is None:
            raise InvalidCredentials()
        async with self.ctx.database.session() as session:
            login = await session.scalar(select(User.login).where(User.id == principal.user_id))
        if login is None:
            raise InvalidCredentials()
        user_id = await self.verify_credentials(login, password, client_ip=client_ip)
        if user_id != principal.user_id:
            raise InvalidCredentials()


def _state_details(user: User) -> dict[str, str]:
    details = {"state": user.state}
    if user.state == AccountState.PENDING_DELETION.value and user.deletion_due_at is not None:
        details["deletion_cancellable_until"] = user.deletion_due_at.isoformat()
    return details
