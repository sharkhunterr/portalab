"""Registration and verification (T028; decision CD-036 for ``invite_only``).

* ``open``: anyone may register; the account waits in Pending Verification until its token is used.
* ``invite_only`` (default): self-registration is closed; the Admin creates accounts (``POST /users``) and
  hands the one-time verification token to the person, who sets a password while verifying.

Verification tokens are 256-bit, stored hashed, single use, expiring (``identity.verificationTtlHours``).
They reach people through the ``VerificationChannel`` port: the baseline is the Admin hand-off (token shown
once to the Admin); Notifications (010) adds e-mail delivery later.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.core.errors import BadRequest, Conflict, Forbidden
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import Credential, VerificationToken
from portalab.modules.identity.services.account_service import AccountService, LoginTaken
from portalab.modules.identity.services.common import SYSTEM, admin_actor
from portalab.modules.identity.services.credentials import (
    CredentialHasher,
    PasswordRejected,
    check_password_policy,
    set_password,
)
from portalab.modules.identity.services.onboarding import OnboardingService
from portalab.modules.identity.services.sessions import hash_token, new_token


class RegistrationClosed(Forbidden):
    default_code = "auth.registration_closed"
    default_title = "Registration is closed"


class InvalidToken(BadRequest):
    default_code = "auth.invalid_token"
    default_title = "Invalid or expired token"

    def __init__(self) -> None:
        super().__init__("This link is invalid or has expired. Ask for a new one.")


class LoginAlreadyUsed(Conflict):
    default_code = "user.login_taken"
    default_title = "Login already in use"


class VerificationChannel(Protocol):
    async def deliver(self, user_id: UUID, token: str, expires_at: datetime) -> None: ...


class AdminHandoffChannel:
    """Baseline channel: nothing is sent; the Admin obtains the token from the admin API and hands it over."""

    async def deliver(self, user_id: UUID, token: str, expires_at: datetime) -> None:
        return None


class CapabilityChannel:
    """Delivers through the ``identity.verification_channel`` provider when one exists (e-mail, 010),
    else falls back to the Admin hand-off. Resolved at each delivery (providers may arrive later)."""

    def __init__(self, capabilities: Any) -> None:
        self.capabilities = capabilities

    async def deliver(self, user_id: UUID, token: str, expires_at: datetime) -> None:
        from portalab.capabilities.identity_directory import VERIFICATION_CHANNEL

        try:
            providers = self.capabilities.system_providers(VERIFICATION_CHANNEL)
        except Exception:
            providers = []
        if providers:
            await providers[0].provider.deliver(user_id, token, expires_at)


@dataclass(frozen=True, slots=True)
class IssuedToken:
    user_id: UUID
    token: str
    expires_at: datetime


class RegistrationService:
    def __init__(
        self,
        ctx: IdentityContext,
        accounts: AccountService,
        hasher: CredentialHasher,
        onboarding: OnboardingService,
        channel: VerificationChannel | None = None,
    ) -> None:
        self.ctx = ctx
        self.accounts = accounts
        self.hasher = hasher
        self.onboarding = onboarding
        self.channel = channel or CapabilityChannel(ctx.capabilities)

    async def _issue(self, session: AsyncSession, user_id: UUID, now: datetime) -> IssuedToken:
        await session.execute(
            update(VerificationToken)
            .where(VerificationToken.user_id == user_id, VerificationToken.consumed_at.is_(None))
            .values(consumed_at=now)  # a new token supersedes the previous ones
        )
        token = new_token()
        expires_at = now + timedelta(hours=self.ctx.config.verification_ttl_hours)
        session.add(
            VerificationToken(
                user_id=user_id,
                token_hash=hash_token(token),
                purpose="verify",
                created_at=now,
                expires_at=expires_at,
            )
        )
        await session.flush()
        return IssuedToken(user_id, token, expires_at)

    async def register(self, *, login: str, display_name: str, password: str, email: str | None) -> None:
        """Self-registration (``open`` mode). The answer never tells whether the login already exists."""
        if self.ctx.config.registration_mode != "open":
            raise RegistrationClosed("Accounts are created by the administrator.")
        check_password_policy(password, self.ctx.config.password_policy)
        now = self.ctx.now()
        issued: IssuedToken | None = None
        try:
            async with self.ctx.database.unit_of_work() as uow:
                user = await self.accounts.create_user(
                    uow.session,
                    login=login,
                    display_name=display_name,
                    email=email,
                    state=AccountState.PENDING_VERIFICATION,
                    actor=SYSTEM,
                    reason="self_registration",
                )
                await set_password(uow.session, self.hasher, user.id, password, now)
                issued = await self._issue(uow.session, user.id, now)
        except LoginTaken:
            await self.hasher.hash(password)  # same work as the success path
            return
        assert issued is not None
        await self.channel.deliver(issued.user_id, issued.token, issued.expires_at)

    async def admin_create(
        self, principal: Principal, *, login: str, display_name: str, email: str | None
    ) -> IssuedToken:
        """Account created by the Admin (``invite_only``); the returned token is shown once."""
        now = self.ctx.now()
        try:
            async with self.ctx.database.unit_of_work() as uow:
                user = await self.accounts.create_user(
                    uow.session,
                    login=login,
                    display_name=display_name,
                    email=email,
                    state=AccountState.PENDING_VERIFICATION,
                    actor=admin_actor(principal),
                    reason="admin_created",
                )
                issued = await self._issue(uow.session, user.id, now)
        except LoginTaken as exc:
            raise LoginAlreadyUsed("This login is already in use.") from exc
        await self.channel.deliver(issued.user_id, issued.token, issued.expires_at)
        return issued

    async def reissue(self, principal: Principal, user_id: UUID) -> IssuedToken:
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            user = await self.accounts.get_for_update(uow.session, user_id)
            if user.state != AccountState.PENDING_VERIFICATION.value:
                raise Conflict(
                    "Only accounts waiting for verification get a new token.", code="user.already_verified"
                )
            issued = await self._issue(uow.session, user.id, now)
        await self.channel.deliver(issued.user_id, issued.token, issued.expires_at)
        return issued

    async def verify(self, token: str, password: str | None) -> UUID:
        """Consume a verification token: Pending Verification → Active, onboarding starts."""
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            row = (
                await uow.session.execute(
                    select(VerificationToken)
                    .where(VerificationToken.token_hash == hash_token(token))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None or row.consumed_at is not None or row.expires_at <= now:
                raise InvalidToken()
            user = await self.accounts.get_for_update(uow.session, row.user_id)
            if user.state != AccountState.PENDING_VERIFICATION.value:
                raise InvalidToken()
            has_credential = await uow.session.get(Credential, user.id) is not None
            if not has_credential:
                if password is None:
                    raise PasswordRejected(
                        "Choose a password to activate the account.", code="user.password_required"
                    )
                check_password_policy(password, self.ctx.config.password_policy)
                await set_password(uow.session, self.hasher, user.id, password, now)
            row.consumed_at = now
            await self.accounts.transition(uow.session, user, AccountState.ACTIVE, SYSTEM, reason="verified")
            await self.onboarding.start(uow.session, user.id, now)
            return user.id


async def latest_token_expiry(session: AsyncSession, user_id: UUID) -> datetime | None:
    expires_at: datetime | None = await session.scalar(
        select(VerificationToken.expires_at)
        .where(VerificationToken.user_id == user_id)
        .order_by(VerificationToken.expires_at.desc())
        .limit(1)
    )
    return expires_at
