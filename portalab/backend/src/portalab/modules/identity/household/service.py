"""Households (spec 032): a member account (the master) holds profiles — members of their own without a
login, used through the master's session. The session remembers which household member it acts as;
entering a protected member — a profile, or the master from a profile — asks its PIN, whoever comes from.
Every household member sees the household's figures; only the master manages it, and it decides on its
profiles' access requests. Nothing here touches a connected service."""

import time
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.economy import ECONOMY
from portalab.capabilities.household import Restrictions
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.statistics import PROGRESSION
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, Forbidden, NotFound
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.display_name import clean_display_name
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.household.rules import (
    COLORS,
    MAX_PROFILES,
    PROFILE_KINDS,
    HouseholdDisabled,
    OwnerOnly,
    ProfileLimit,
    RestrictionSettings,
    WrongPin,
    check_pin,
    color_for,
    parse,
    preset,
)
from portalab.modules.identity.models import (
    AccessRequest,
    HouseholdMember,
    Profile,
    User,
    UserSession,
)
from portalab.modules.identity.services.account_service import AccountService
from portalab.modules.identity.services.common import Actor, Throttled, audit, log, self_actor, user_ref
from portalab.modules.identity.services.credentials import CredentialHasher
from portalab.modules.identity.services.onboarding import OnboardingService
from portalab.modules.identity.services.throttle import LoginThrottleService, throttle_key
from portalab.modules.identity.services.visits import record_visit
from portalab.modules.identity.settings import HOUSEHOLD_ENABLED, HOUSEHOLD_MAX

CACHE_S = 15.0
CATEGORY = "identity.household"
LIVE = AccountState.ACTIVE.value


def household_of(principal: Principal) -> UUID:
    """The household's master for whoever acts (a profile's master, else the member themself)."""
    owner = principal.profile_of or principal.user_id
    if owner is None or principal.channel != "user":
        raise Forbidden("Sign in to use profiles.", code="household.signed_out")
    return owner


class HouseholdService:
    def __init__(
        self,
        ctx: IdentityContext,
        hasher: CredentialHasher,
        accounts: AccountService,
        throttle: LoginThrottleService,
        onboarding: OnboardingService,
    ) -> None:
        self.ctx = ctx
        self.hasher = hasher
        self.accounts = accounts
        self.throttle = throttle
        self.onboarding = onboarding
        self.deletion: Any = None  # wired by the module (the deletion saga needs the sessions)
        self._owners: dict[UUID, UUID | None] = {}
        self._restrictions: dict[UUID, tuple[float, Restrictions | None]] = {}
        self._hidden: tuple[float, frozenset[UUID]] | None = None

    # --- settings ------------------------------------------------------------------------------------
    async def settings(self) -> tuple[bool, int]:
        """Whether profiles are offered, and how many an account may hold (administrators choose)."""
        values: dict[str, Any] = {HOUSEHOLD_ENABLED: True, HOUSEHOLD_MAX: MAX_PROFILES}
        providers = self.ctx.capabilities.system_providers(CONFIG)
        for key in values:
            try:
                if providers:
                    values[key] = (await providers[0].provider.get(key)).value
            except Exception:  # noqa: S112 — the default stands
                continue
        limit = values[HOUSEHOLD_MAX]
        return values[HOUSEHOLD_ENABLED] is not False, max(1, min(int(limit), 20)) if isinstance(
            limit, int
        ) else MAX_PROFILES

    async def _enabled(self) -> int:
        enabled, limit = await self.settings()
        if not enabled:
            raise HouseholdDisabled("Profiles are switched off on this portal.")
        return limit

    def forget(self, *users: UUID) -> None:
        for user in users:
            self._restrictions.pop(user, None)
        self._hidden = None

    # --- reads for other modules (``identity.household``) ---------------------------------------------
    async def owner_of(self, user: UUID) -> UUID | None:
        if user in self._owners:
            return self._owners[user]
        async with self.ctx.database.session() as session:
            owner = await session.scalar(
                select(HouseholdMember.owner_id).where(
                    HouseholdMember.user_id == user, HouseholdMember.kind != "owner"
                )
            )
        if len(self._owners) > 10_000:
            self._owners.clear()
        self._owners[user] = owner  # a user never becomes, nor stops being, a profile
        return owner

    async def restrictions_of(self, user: UUID) -> Restrictions | None:
        cached = self._restrictions.get(user)
        if cached is not None and time.monotonic() - cached[0] < CACHE_S:
            return cached[1]
        async with self.ctx.database.session() as session:
            row = await session.get(HouseholdMember, user)
        found = None
        if row is not None and row.kind != "owner":
            restrictions = parse(row.restrictions).restrictions()
            found = restrictions if restrictions.limits_titles or restrictions.blocked else None
        self._restrictions[user] = (time.monotonic(), found)
        return found

    async def grants(self, user: UUID, kind: str) -> frozenset[str]:
        now = self.ctx.now()
        async with self.ctx.database.session() as session:
            refs = await session.scalars(
                select(AccessRequest.subject_ref).where(
                    AccessRequest.profile_id == user,
                    AccessRequest.kind == kind,
                    AccessRequest.status == "approved",
                    (AccessRequest.expires_at.is_(None)) | (AccessRequest.expires_at > now),
                )
            )
            return frozenset(refs)

    async def granted(self, user: UUID, kind: str, ref: str) -> bool:
        return ref in await self.grants(user, kind)

    async def hidden(self) -> frozenset[UUID]:
        if self._hidden is not None and time.monotonic() - self._hidden[0] < CACHE_S:
            return self._hidden[1]
        async with self.ctx.database.session() as session:
            found = frozenset(
                await session.scalars(
                    select(HouseholdMember.user_id).where(
                        HouseholdMember.kind != "owner", HouseholdMember.community_visible.is_(False)
                    )
                )
            )
        self._hidden = (time.monotonic(), found)
        return found

    # --- the session ---------------------------------------------------------------------------------
    async def acting(self, session: AsyncSession, row: UserSession) -> UUID | None:
        """The live profile a session acts as, or ``None`` when that profile is no longer usable."""
        if row.acting_user_id is None:
            return None
        found: UUID | None = await session.scalar(
            select(HouseholdMember.user_id)
            .join(User, User.id == HouseholdMember.user_id)
            .where(
                HouseholdMember.user_id == row.acting_user_id,
                HouseholdMember.owner_id == row.user_id,
                HouseholdMember.kind != "owner",
                User.state == LIVE,
            )
        )
        return found

    async def _members(self, session: AsyncSession, owner: UUID) -> list[tuple[User, HouseholdMember | None]]:
        """The master first, then its live profiles in their order."""
        master = await session.get(User, owner)
        if master is None:
            return []
        rows = (
            await session.execute(
                select(User, HouseholdMember)
                .join(HouseholdMember, HouseholdMember.user_id == User.id)
                .where(HouseholdMember.owner_id == owner, User.state == LIVE)
                .order_by(HouseholdMember.kind != "owner", HouseholdMember.position, User.created_at)
            )
        ).all()
        members: list[tuple[User, HouseholdMember | None]] = [(u, m) for u, m in rows]
        if not members or members[0][0].id != owner:
            members.insert(0, (master, None))
        return members

    @staticmethod
    def _tile(user: User, member: HouseholdMember | None, avatar: bool) -> dict[str, Any]:
        return {
            "id": user.id,
            "display_name": user.display_name or "",
            "kind": member.kind if member is not None else "owner",
            "color": member.color if member is not None else color_for(None, 0),
            "has_avatar": avatar,
            "has_pin": member is not None and member.pin_hash is not None,
        }

    async def _avatars(self, session: AsyncSession, users: list[UUID]) -> set[UUID]:
        return set(
            await session.scalars(
                select(Profile.user_id).where(
                    Profile.user_id.in_(users), Profile.avatar_blob_key.is_not(None)
                )
            )
        )

    async def state(self, principal: Principal) -> dict[str, Any]:
        """For the « Who's there? » picker: the household's members, who is active, whether to choose."""
        owner = household_of(principal)
        enabled, _ = await self.settings()
        async with self.ctx.database.session() as session:
            members = await self._members(session, owner)
            avatars = await self._avatars(session, [u.id for u, _ in members])
            chosen = True
            if principal.session_id is not None:
                chosen = bool(
                    await session.scalar(
                        select(UserSession.profile_chosen).where(UserSession.id == principal.session_id)
                    )
                )
        tiles = []
        for user, member in members:
            tile = self._tile(user, member, user.id in avatars)
            # entering a protected member asks its PIN, whoever comes from (the master too)
            tile["needs_pin"] = tile["has_pin"] and user.id != principal.user_id
            tiles.append(tile)
        profiles = len(tiles) > 1
        return {
            "enabled": enabled,
            "owner_id": owner,
            "active_id": principal.user_id,
            "must_choose": enabled and profiles and not chosen,
            "members": tiles if enabled else tiles[:1],
        }

    async def switch(self, principal: Principal, target: UUID, pin: str | None) -> dict[str, Any]:
        owner = household_of(principal)
        await self._enabled()
        if principal.session_id is None:
            raise Forbidden("Profiles are used from a signed-in browser.", code="household.no_session")
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            member = await uow.session.get(HouseholdMember, target)
            user = await uow.session.get(User, target)
            belongs = target == owner or (
                member is not None and member.owner_id == owner and member.kind != "owner"
            )
            if not belongs or user is None or user.state != LIVE:
                raise NotFound("This profile does not exist.", code="household.member_not_found")
            if target != principal.user_id and member is not None and member.pin_hash is not None:
                await self._check_pin(member.user_id, member.pin_hash, pin or "", now)
            await uow.session.execute(
                update(UserSession)
                .where(UserSession.id == principal.session_id, UserSession.user_id == owner)
                .values(acting_user_id=None if target == owner else target, profile_chosen=True)
            )
            if target != owner:
                user.last_sign_in_at = now  # a profile lives by its use (never dormant while used)
                await record_visit(self.ctx, uow.session, target, now)
        log.info("household profile switched", extra={"fields": {"to_owner": target == owner}})
        return {"active_id": target}

    async def _check_pin(self, member: UUID, pin_hash: str, pin: str, now: datetime) -> None:
        """A wrong PIN is counted in a transaction of its own (the refused operation's rolls back)."""
        key, right = throttle_key(f"household-pin:{member}", None), False
        async with self.ctx.database.unit_of_work() as uow:
            blocked = await self.throttle.blocked_until(uow.session, key, now)
            if blocked is None:
                right = await self.hasher.verify(pin_hash, pin)
                if right:
                    await self.throttle.clear(uow.session, key)
                else:
                    await self.throttle.record_failure(uow.session, key, now)
        if blocked is not None:
            raise Throttled(
                "Too many wrong PINs; try again later.",
                code="household.pin_throttled",
                extensions={"retry_after": max(1, int((blocked - now).total_seconds()))},
            )
        if not right:
            raise WrongPin("This PIN is not the right one.")

    # --- the household page --------------------------------------------------------------------------
    async def overview(self, principal: Principal) -> dict[str, Any]:
        """Every household member sees the household: its wallet (the master's balances, which hold every
        profile's earnings) and each member's figures; the restrictions to the master and to the profile."""
        owner = household_of(principal)
        enabled, limit = await self.settings()
        async with self.ctx.database.session() as session:
            members = await self._members(session, owner)
            avatars = await self._avatars(session, [u.id for u, _ in members])
        manager = principal.profile_of is None
        tiles = []
        for user, member in members:
            tile = self._tile(user, member, user.id in avatars)
            tile["progress"] = await self._progress(user.id)
            tile["community_visible"] = member.community_visible if member is not None else True
            if member is not None and member.kind != "owner" and (manager or user.id == principal.user_id):
                settings = parse(member.restrictions)
                tile["restrictions"] = settings.model_dump(mode="json")
                tile["age"] = settings.age(self.ctx.now().date())
                tile["effective_age"] = settings.effective_age(self.ctx.now().date())
            tiles.append(tile)
        return {
            "enabled": enabled,
            "owner_id": owner,
            "me": principal.user_id,
            "can_manage": manager and enabled,
            "max_profiles": limit,
            "palette": list(COLORS),
            "totals": tiles[0]["progress"] if tiles else None,
            "members": tiles,
        }

    async def _progress(self, user: UUID) -> dict[str, int]:
        empty = {"xp": 0, "level": 0, "coins": 0, "contribution": 0}
        providers = self.ctx.capabilities.system_providers(PROGRESSION)
        if not providers or not hasattr(providers[0].provider, "progress"):
            return empty
        try:
            progress = await providers[0].provider.progress(user)
        except Exception:
            return empty
        return {
            "xp": int(progress.xp),
            "level": int(progress.level),
            "coins": int(progress.coins),
            "contribution": int(progress.contribution),
        }

    # --- management (the master only) ----------------------------------------------------------------
    @staticmethod
    def _manager(principal: Principal) -> UUID:
        owner = household_of(principal)
        if principal.profile_of is not None:
            raise OwnerOnly("Only the account's master manages its profiles.")
        return owner

    async def _profile(
        self, session: AsyncSession, owner: UUID, profile: UUID
    ) -> tuple[User, HouseholdMember]:
        member = await session.get(HouseholdMember, profile, with_for_update=True)
        user = await session.get(User, profile)
        if member is None or member.owner_id != owner or member.kind == "owner" or user is None:
            raise NotFound("This profile does not exist.", code="household.member_not_found")
        if user.state != LIVE:
            raise NotFound("This profile does not exist.", code="household.member_not_found")
        return user, member

    async def _owner_row(self, session: AsyncSession, owner: UUID, now: datetime) -> HouseholdMember:
        row = await session.get(HouseholdMember, owner, with_for_update=True)
        if row is None:
            row = HouseholdMember(
                user_id=owner,
                owner_id=owner,
                kind="owner",
                color=color_for(None, 0),
                position=0,
                community_visible=True,
                restrictions={},
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
        return row

    async def create(
        self, principal: Principal, *, display_name: str, kind: str, color: str | None, pin: str | None
    ) -> dict[str, Any]:
        owner = self._manager(principal)
        limit = await self._enabled()
        if kind not in PROFILE_KINDS:
            raise Conflict("Choose standard, child or custom.", code="household.invalid_kind")
        pin_hash = await self.hasher.hash(check_pin(pin)) if pin else None
        now = self.ctx.now()
        actor = self_actor(principal)
        async with self.ctx.database.unit_of_work() as uow:
            await self._owner_row(uow.session, owner, now)
            count = int(
                await uow.session.scalar(
                    select(func.count())
                    .select_from(HouseholdMember)
                    .join(User, User.id == HouseholdMember.user_id)
                    .where(
                        HouseholdMember.owner_id == owner,
                        HouseholdMember.kind != "owner",
                        User.state.not_in(("deleted", "pending_deletion")),
                    )
                )
                or 0
            )
            if count >= limit:
                raise ProfileLimit(f"An account holds at most {limit} profiles.", extensions={"limit": limit})
            user = await self.accounts.create_user(
                uow.session,
                login=None,
                display_name=display_name,
                email=None,
                state=AccountState.ACTIVE,
                actor=actor,
                reason="household_profile",
                unique_name=False,
            )
            restrictions, visible = preset(kind)
            uow.session.add(
                HouseholdMember(
                    user_id=user.id,
                    owner_id=owner,
                    kind=kind,
                    color=color_for(color, count + 1),
                    position=count + 1,
                    pin_hash=pin_hash,
                    community_visible=visible,
                    restrictions=restrictions.model_dump(mode="json"),
                    created_at=now,
                    updated_at=now,
                )
            )
            await self.onboarding.start(uow.session, user.id, now)
            await audit(
                self.ctx,
                uow.session,
                "household.profile_created",
                principal,
                resource=user_ref(user.id),
                context={"kind": kind},
            )
        self._owners[user.id] = owner
        self.forget(user.id)
        return {"id": user.id}

    async def change(
        self,
        principal: Principal,
        profile: UUID,
        *,
        display_name: str | None = None,
        color: str | None = None,
        kind: str | None = None,
        restrictions: RestrictionSettings | None = None,
        community_visible: bool | None = None,
        position: int | None = None,
    ) -> None:
        owner = self._manager(principal)
        await self._enabled()
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            user, member = await self._profile(uow.session, owner, profile)
            if display_name is not None:
                user.display_name = clean_display_name(display_name)
                user.updated_at = now
            if color is not None:
                member.color = color_for(color, member.position)
            if kind is not None and kind != member.kind:
                if kind not in PROFILE_KINDS:
                    raise Conflict("Choose standard, child or custom.", code="household.invalid_kind")
                member.kind = kind
                if restrictions is None:
                    settings, visible = preset(kind)
                    member.restrictions = settings.model_dump(mode="json")
                    if community_visible is None:
                        member.community_visible = visible
            if restrictions is not None:
                member.restrictions = restrictions.model_dump(mode="json")
            if community_visible is not None:
                member.community_visible = community_visible
            if position is not None:
                member.position = max(1, min(position, 99))
            member.updated_at = now
            await audit(
                self.ctx,
                uow.session,
                "household.profile_changed",
                principal,
                resource=user_ref(profile),
                context={"kind": member.kind, "restrictions": member.restrictions},
            )
        self.forget(profile)

    async def set_pin(
        self, principal: Principal, member_id: UUID, pin: str | None, current: str | None = None
    ) -> None:
        """The master sets or removes any member's PIN (its own included); a profile, its own — giving the
        one it replaces."""
        owner = household_of(principal)
        await self._enabled()
        if principal.profile_of is not None and member_id != principal.user_id:
            raise OwnerOnly("Only the account's master changes another profile's PIN.")
        pin_hash = await self.hasher.hash(check_pin(pin)) if pin else None
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            if member_id == owner:
                member = await self._owner_row(uow.session, owner, now)
            else:
                _, member = await self._profile(uow.session, owner, member_id)
            if principal.profile_of is not None and member.pin_hash is not None:
                await self._check_pin(member.user_id, member.pin_hash, current or "", now)
            member.pin_hash = pin_hash
            member.updated_at = now
            await audit(
                self.ctx,
                uow.session,
                "household.pin_changed",
                principal,
                resource=user_ref(member_id),
                context={"set": pin_hash is not None},
            )

    async def remove(self, principal: Principal, profile: UUID) -> None:
        """The profile follows an account's deletion (at once: nobody signs in to cancel it); every browser
        using it is signed out."""
        owner = self._manager(principal)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await self._profile(uow.session, owner, profile)
            await uow.session.execute(
                update(UserSession)
                .where(UserSession.acting_user_id == profile, UserSession.revoked_at.is_(None))
                .values(revoked_at=now, revoke_reason="admin")
            )
        await self.deletion.request(Actor("self", principal), profile, reason="household", grace=timedelta(0))
        self.forget(profile)

    # --- supervision ---------------------------------------------------------------------------------
    async def activity(self, principal: Principal, profile: UUID) -> dict[str, Any]:
        """What a profile earned and spent lately, and its access requests — for its master (and itself)."""
        owner = household_of(principal)
        if principal.profile_of is not None and profile != principal.user_id:
            raise OwnerOnly("Only the account's master reads its profiles' activity.")
        async with self.ctx.database.session() as session:
            member = await session.get(HouseholdMember, profile)
            if member is None or member.owner_id != owner or member.kind == "owner":
                raise NotFound("This profile does not exist.", code="household.member_not_found")
            seen = await session.scalar(select(User.last_sign_in_at).where(User.id == profile))
        economy: list[dict[str, Any]] = []
        providers = self.ctx.capabilities.system_providers(ECONOMY)
        if providers:
            try:
                page = await providers[0].provider.history(profile, limit=40)
                economy = [
                    {
                        "value": tx.value,
                        "delta": tx.delta,
                        "kind": tx.kind,
                        "source": tx.source_kind,
                        "rule": tx.rule_key,
                        "reason": tx.reason,
                        "at": tx.occurred_at,
                    }
                    for tx in page.items
                ]
            except Exception:
                log.warning("household activity: economy history unavailable")
        return {"last_seen_at": seen, "economy": economy, "requests": await self.requests(principal, profile)}

    # --- access requests -----------------------------------------------------------------------------
    @staticmethod
    def _request(row: AccessRequest, names: dict[UUID, str]) -> dict[str, Any]:
        return {
            "id": row.id,
            "profile_id": row.profile_id,
            "profile_name": names.get(row.profile_id, ""),
            "kind": row.kind,
            "subject_ref": row.subject_ref,
            "title": row.title,
            "rating": row.rating,
            "note": row.note,
            "status": row.status,
            "created_at": row.created_at,
            "decided_at": row.decided_at,
            "expires_at": row.expires_at,
        }

    async def requests(self, principal: Principal, profile: UUID | None = None) -> list[dict[str, Any]]:
        """The master: its profiles' requests (pending first); a profile: its own."""
        owner = household_of(principal)
        if principal.profile_of is not None:
            profile = principal.user_id
        statement = select(AccessRequest).where(AccessRequest.owner_id == owner)
        if profile is not None:
            statement = statement.where(AccessRequest.profile_id == profile)
        async with self.ctx.database.session() as session:
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(
                            AccessRequest.status != "pending", AccessRequest.created_at.desc()
                        ).limit(60)
                    )
                ).all()
            )
            ids = {row.profile_id for row in rows}
            names = {
                u.id: u.display_name or ""
                for u in (await session.scalars(select(User).where(User.id.in_(ids)))).all()
            }
        return [self._request(row, names) for row in rows]

    async def ask(
        self, principal: Principal, *, kind: str, ref: str, title: str, rating: str | None, note: str | None
    ) -> dict[str, Any]:
        owner = household_of(principal)
        await self._enabled()
        if principal.profile_of is None or principal.user_id is None:
            raise Forbidden("Only a profile asks its master for access.", code="household.not_a_profile")
        restrictions = await self.restrictions_of(principal.user_id)
        if restrictions is not None and not restrictions.requests:
            raise Forbidden("Your profile cannot ask for access.", code="household.requests_off")
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            pending = await uow.session.scalar(
                select(AccessRequest).where(
                    AccessRequest.profile_id == principal.user_id,
                    AccessRequest.kind == kind,
                    AccessRequest.subject_ref == ref,
                    AccessRequest.status == "pending",
                )
            )
            if pending is not None:
                return {"id": pending.id, "status": "pending", "created": False}
            row = AccessRequest(
                profile_id=principal.user_id,
                owner_id=owner,
                kind=kind,
                subject_ref=ref[:200],
                title=title.strip()[:300] or ref[:300],
                rating=(rating or "").strip()[:32] or None,
                note=(note or "").strip()[:300] or None,
                status="pending",
                created_at=now,
            )
            uow.session.add(row)
            await uow.session.flush()
            name = await uow.session.scalar(select(User.display_name).where(User.id == principal.user_id))
        await self._notify(
            owner,
            "household:notify.request",
            {"profile": name or "", "title": row.title},
            f"household:request:{row.id}",
            "/household?tab=requests",
        )
        return {"id": row.id, "status": "pending", "created": True}

    async def decide(self, principal: Principal, request: UUID, *, approve: bool, days: int | None) -> None:
        owner = self._manager(principal)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            row = await uow.session.get(AccessRequest, request, with_for_update=True)
            if row is None or row.owner_id != owner:
                raise NotFound("This request does not exist.", code="household.request_not_found")
            if row.status != "pending":
                raise Conflict("This request was already answered.", code="household.request_answered")
            row.status = "approved" if approve else "denied"
            row.decided_at = now
            row.expires_at = now + timedelta(days=days) if approve and days else None
            await audit(
                self.ctx,
                uow.session,
                "household.access_decided",
                principal,
                resource=user_ref(row.profile_id),
                context={"kind": row.kind, "ref": row.subject_ref, "approved": approve, "days": days},
            )
        await self._notify(
            row.profile_id,
            f"household:notify.{row.status}",
            {"title": row.title, "days": days or 0},
            f"household:decision:{row.id}",
            f"/media/{row.subject_ref}" if row.kind == "media" else "/household",
        )

    async def _notify(self, user: UUID, template: str, params: dict[str, Any], dedup: str, url: str) -> None:
        try:
            providers = self.ctx.capabilities.system_providers(NOTIFY)
            if providers:
                await providers[0].provider.send(
                    CommunicationRequest(
                        category=CATEGORY,
                        template_key=template,
                        audience=Users((user,)),
                        dedup_key=dedup,
                        params=params,
                        subject_ref=dedup,
                        action_url=url,
                    )
                )
        except Exception:
            log.warning("household notification not sent")
