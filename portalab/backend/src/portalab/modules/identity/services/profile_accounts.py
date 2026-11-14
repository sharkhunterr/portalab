"""``identity.profile_accounts`` (spec 032): the accounts behind household profiles — members without a login,
used through their master's session — for the household module, which owns the households themselves.
PINs are hashed and throttled like passwords (Argon2 stays here)."""

from collections.abc import Mapping, Sequence
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, update

from portalab.capabilities.household import AccountCard, PinThrottled, WrongPin
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.display_name import clean_display_name
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import Profile, User, UserSession
from portalab.modules.identity.services.account_service import AccountService
from portalab.modules.identity.services.common import Actor, self_actor
from portalab.modules.identity.services.credentials import CredentialHasher
from portalab.modules.identity.services.deletion import DeletionService
from portalab.modules.identity.services.onboarding import OnboardingService
from portalab.modules.identity.services.throttle import LoginThrottleService, throttle_key
from portalab.modules.identity.services.visits import record_visit

LIVE = AccountState.ACTIVE.value


class ProfileAccountsService:
    def __init__(
        self,
        ctx: IdentityContext,
        accounts: AccountService,
        onboarding: OnboardingService,
        hasher: CredentialHasher,
        throttle: LoginThrottleService,
        deletion: DeletionService,
    ) -> None:
        self.ctx = ctx
        self.accounts = accounts
        self.onboarding = onboarding
        self.hasher = hasher
        self.throttle = throttle
        self.deletion = deletion

    async def create(self, display_name: str, actor: Principal) -> UUID:
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            user = await self.accounts.create_user(
                uow.session,
                login=None,
                display_name=display_name,
                email=None,
                state=AccountState.ACTIVE,
                actor=self_actor(actor),
                reason="household_profile",
                unique_name=False,
            )
            await self.onboarding.start(uow.session, user.id, now)
            return user.id

    async def rename(self, user: UUID, display_name: str) -> None:
        async with self.ctx.database.unit_of_work() as uow:
            row = await uow.session.get(User, user, with_for_update=True)
            if row is None:
                raise NotFound("This profile does not exist.", code="household.member_not_found")
            row.display_name = clean_display_name(display_name)
            row.updated_at = self.ctx.now()

    async def remove(self, user: UUID, actor: Principal) -> None:
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await uow.session.execute(
                update(UserSession)
                .where(UserSession.acting_user_id == user, UserSession.revoked_at.is_(None))
                .values(revoked_at=now, revoke_reason="admin")
            )
        await self.deletion.request(Actor("self", actor), user, reason="household", grace=timedelta(0))

    async def cards(self, users: Sequence[UUID]) -> Mapping[UUID, AccountCard]:
        if not users:
            return {}
        async with self.ctx.database.session() as session:
            rows = (
                await session.execute(
                    select(User.id, User.display_name, User.state, User.last_sign_in_at).where(
                        User.id.in_(list(users))
                    )
                )
            ).all()
            avatars = set(
                await session.scalars(
                    select(Profile.user_id).where(
                        Profile.user_id.in_(list(users)), Profile.avatar_blob_key.is_not(None)
                    )
                )
            )
        return {
            row.id: AccountCard(
                id=row.id,
                display_name=row.display_name or "",
                has_avatar=row.id in avatars,
                live=row.state == LIVE,
                last_seen_at=row.last_sign_in_at,
            )
            for row in rows
        }

    async def act(self, session_id: UUID, owner: UUID, target: UUID | None) -> None:
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await uow.session.execute(
                update(UserSession)
                .where(UserSession.id == session_id, UserSession.user_id == owner)
                .values(acting_user_id=target, profile_chosen=True)
            )
            if target is not None:
                profile = await uow.session.get(User, target, with_for_update=True)
                if profile is not None:
                    profile.last_sign_in_at = now  # a profile lives by its use
                    await record_visit(self.ctx, uow.session, target, now)

    async def chosen(self, session_id: UUID) -> bool:
        async with self.ctx.database.session() as session:
            return bool(
                await session.scalar(select(UserSession.profile_chosen).where(UserSession.id == session_id))
            )

    async def hash_pin(self, pin: str) -> str:
        return await self.hasher.hash(pin)

    async def verify_pin(self, subject: UUID, pin_hash: str, pin: str) -> None:
        """A wrong PIN is counted in a transaction of its own (the refused operation's rolls back)."""
        now = self.ctx.now()
        key, right = throttle_key(f"household-pin:{subject}", None), False
        async with self.ctx.database.unit_of_work() as uow:
            blocked = await self.throttle.blocked_until(uow.session, key, now)
            if blocked is None:
                right = await self.hasher.verify(pin_hash, pin)
                if right:
                    await self.throttle.clear(uow.session, key)
                else:
                    await self.throttle.record_failure(uow.session, key, now)
        if blocked is not None:
            raise PinThrottled(
                "Too many wrong PINs; try again later.",
                extensions={"retry_after": max(1, int((blocked - now).total_seconds()))},
            )
        if not right:
            raise WrongPin("This PIN is not the right one.")
