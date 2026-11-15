"""Households (spec 032): a member account (the master) holds profiles — members of their own without a login,
used through the master's session. Entering a protected member — a profile, or the master from a profile —
asks its PIN, whoever comes from. Every household member sees the household's figures; only the master
manages it, sets each profile's policy and decides on its profiles' access requests.

The households are this module's; the accounts behind them, the sessions and the PINs' hashing are
identity's (``identity.profile_accounts``). Nothing here touches a connected service."""

import time
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.economy import ECONOMY, HOUSEHOLD_POT
from portalab.capabilities.household import PROFILE_ACCOUNTS, AccountCard, ProfileAccounts, Restrictions
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import PROGRESSION
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound, Unavailable
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.household.models import AccessRequest, HouseholdMember
from portalab.modules.household.rules import (
    COLORS,
    MAX_PROFILES,
    PROFILE_KINDS,
    OwnerOnly,
    ProfileLimit,
    RestrictionSettings,
    check_pin,
    color_for,
    parse,
    preset,
)
from portalab.modules.household.settings import MAX_KEY

CACHE_S = 15.0
ECONOMIES = ("pot", "dispatch")  # issue 443
ATTENTION_ENTRY = "shell.household.requests"  # issue 428: « My household »'s requests tab
CATEGORY = "household.requests"
EXTRA_MINUTES = (15, 30, 60, 120)  # issue 432: screen time given for today
log = get_logger("portalab.household")


def household_of(principal: Principal) -> UUID:
    """The household's master for whoever acts (a profile's master, else the member themself)."""
    owner = principal.profile_of or principal.user_id
    if owner is None or principal.channel != "user":
        raise Forbidden("Sign in to use profiles.", code="household.signed_out")
    return owner


def _ref(user: UUID) -> ResourceRef:
    return ResourceRef(kind="user", id=str(user), owner_id=user)


class HouseholdService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        audit: AuditSink,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.audit = audit
        self.clock = clock
        self._owners: dict[UUID, UUID | None] = {}
        self._restrictions: dict[UUID, tuple[float, Restrictions | None]] = {}
        self._hidden: tuple[float, frozenset[UUID]] | None = None
        self._anonymous: tuple[float, frozenset[UUID]] | None = None
        self._profiles: tuple[float, frozenset[UUID]] | None = None
        self._economies: dict[UUID, tuple[float, str]] = {}

    def now(self) -> datetime:
        return utc_now(self.clock)

    def accounts(self) -> ProfileAccounts:
        providers = self.capabilities.system_providers(PROFILE_ACCOUNTS)
        if not providers:
            raise Unavailable("Accounts are not available.", code="household.unavailable")
        provider: ProfileAccounts = providers[0].provider
        return provider

    async def limit(self) -> int:
        """How many profiles an account may hold (administrators choose)."""
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                value = (await providers[0].provider.get(MAX_KEY)).value
                if isinstance(value, int):
                    return max(1, min(value, 20))
        except Exception:  # noqa: S110 — the default stands
            pass
        return MAX_PROFILES

    def forget(self, *users: UUID) -> None:
        for user in users:
            self._restrictions.pop(user, None)
        self._hidden = None
        self._anonymous = None
        self._profiles = None
        self._economies.clear()

    async def _audit(
        self, session: AsyncSession, action: str, actor: Principal, user: UUID, context: dict[str, Any]
    ) -> None:
        try:
            await self.audit.record(session, AuditRecord(action, actor, resource=_ref(user), context=context))
        except Exception:
            log.error("household audit not written", extra={"fields": {"action": action}})

    # --- reads for other modules (``household.profiles``) ---------------------------------------------
    async def owner_of(self, user: UUID) -> UUID | None:
        if user in self._owners:
            return self._owners[user]
        async with self.database.session() as session:
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
        async with self.database.session() as session:
            row = await session.get(HouseholdMember, user)
        found = None
        free = row is not None and row.free_until is not None and row.free_until > self.now()
        if row is not None and row.kind != "owner" and not free:  # issue 432: no limits for a while
            restrictions = parse(row.restrictions).restrictions(
                bonus_minutes=row.bonus_minutes or 0, bonus_day=row.bonus_day
            )
            found = restrictions if restrictions.restricts else None
        self._restrictions[user] = (time.monotonic(), found)
        return found

    async def grants(self, user: UUID, kind: str) -> frozenset[str]:
        now = self.now()
        async with self.database.session() as session:
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
        """Issue 443: every profile of a common pot — its master stands for the household in the community."""
        if self._hidden is not None and time.monotonic() - self._hidden[0] < CACHE_S:
            return self._hidden[1]
        found = await self._profiles_where(pot=True)
        self._hidden = (time.monotonic(), found)
        return found

    async def anonymous(self) -> frozenset[UUID]:
        """Issue 443: the dispatched profiles their master shows anonymously in the community."""
        if self._anonymous is not None and time.monotonic() - self._anonymous[0] < CACHE_S:
            return self._anonymous[1]
        found = await self._profiles_where(pot=False, visible=False)
        self._anonymous = (time.monotonic(), found)
        return found

    async def _profiles_where(self, *, pot: bool, visible: bool | None = None) -> frozenset[UUID]:
        master = aliased(HouseholdMember)
        economy = func.coalesce(master.economy, "pot")
        query = (
            select(HouseholdMember.user_id)
            .outerjoin(master, master.user_id == HouseholdMember.owner_id)
            .where(HouseholdMember.kind != "owner", (economy == "pot") if pot else (economy == "dispatch"))
        )
        if visible is not None:
            query = query.where(HouseholdMember.community_visible.is_(visible))
        async with self.database.session() as session:
            return frozenset(await session.scalars(query))

    async def exists(self, user: UUID) -> bool:
        """Issue 445: a profile, or a master who made its household (its own row)."""
        async with self.database.session() as session:
            return await session.get(HouseholdMember, user) is not None

    async def make(self, principal: Principal, economy: str) -> None:
        """Issue 445: the master makes its household (once), with its economy — « My household » appears."""
        owner = self._manager(principal)
        if economy not in ECONOMIES:
            raise Conflict("Choose a common pot or dispatched profiles.", code="household.invalid_economy")
        async with self.database.unit_of_work() as uow:
            existing = await uow.session.get(HouseholdMember, owner)
            row = await self._owner_row(uow.session, owner, self.now())
            if existing is None:
                row.economy = economy
                await self._audit(uow.session, "household.made", principal, owner, {"economy": economy})
        self.forget(owner)
        if existing is not None and existing.economy != economy:
            await self.set_economy(principal, economy)

    async def unmake(self, principal: Principal) -> None:
        """Issue 445: a household without profiles undone — « My household » disappears until made again."""
        owner = self._manager(principal)
        if await self.profiles_of(owner):
            raise Conflict("Remove the profiles first.", code="household.not_empty")
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(HouseholdMember, owner, with_for_update=True)
            if row is None:
                return
            await uow.session.delete(row)
            await self._audit(uow.session, "household.unmade", principal, owner, {})
        self.forget(owner)

    async def economy_of(self, user: UUID) -> str:
        """Issue 443: its household's economy — its master's choice (``pot`` until the master chooses)."""
        cached = self._economies.get(user)
        if cached is not None and time.monotonic() - cached[0] < CACHE_S:
            return cached[1]
        async with self.database.session() as session:
            row = await session.get(HouseholdMember, user)
            master = await session.get(HouseholdMember, row.owner_id) if row is not None else None
        found = master.economy if master is not None and master.economy in ECONOMIES else "pot"
        self._economies[user] = (time.monotonic(), found)
        return found

    async def set_economy(self, principal: Principal, economy: str) -> None:
        """Issue 443: the master chooses its household's economy; switching rebuilds the pot (its profiles'
        amounts and items duplicated on the master) or gives it back (each profile keeps its own)."""
        owner = self._manager(principal)
        if economy not in ECONOMIES:
            raise Conflict("Choose a common pot or dispatched profiles.", code="household.invalid_economy")
        async with self.database.unit_of_work() as uow:
            row = await self._owner_row(uow.session, owner, self.now())
            if row.economy == economy:
                return
            row.economy = economy
            row.updated_at = self.now()
            await self._audit(
                uow.session, "household.economy_changed", principal, owner, {"economy": economy}
            )
        self.forget(owner)
        profiles = sorted(await self.profiles_of(owner))
        if not profiles:
            return
        for registration in self.capabilities.system_providers(HOUSEHOLD_POT):
            try:
                await registration.provider.regroup(owner, profiles, economy == "pot")
            except Exception:
                log.exception("household economy not regrouped", extra={"economy": economy})

    async def profiles(self) -> frozenset[UUID]:
        if self._profiles is not None and time.monotonic() - self._profiles[0] < CACHE_S:
            return self._profiles[1]
        async with self.database.session() as session:
            found = frozenset(
                await session.scalars(select(HouseholdMember.user_id).where(HouseholdMember.kind != "owner"))
            )
        self._profiles = (time.monotonic(), found)
        return found

    async def profiles_of(self, owner: UUID) -> frozenset[UUID]:
        async with self.database.session() as session:
            return frozenset(
                await session.scalars(
                    select(HouseholdMember.user_id).where(
                        HouseholdMember.owner_id == owner, HouseholdMember.kind != "owner"
                    )
                )
            )

    # --- the household's members ---------------------------------------------------------------------
    async def _members(self, owner: UUID) -> list[tuple[AccountCard, HouseholdMember | None]]:
        """The master first, then its live profiles in their order."""
        async with self.database.session() as session:
            rows = list(
                (
                    await session.scalars(
                        select(HouseholdMember)
                        .where(HouseholdMember.owner_id == owner)
                        .order_by(HouseholdMember.kind != "owner", HouseholdMember.position)
                    )
                ).all()
            )
        cards = await self.accounts().cards([owner, *(r.user_id for r in rows)])
        master = cards.get(owner)
        if master is None:
            return []
        members: list[tuple[AccountCard, HouseholdMember | None]] = [
            (master, next((r for r in rows if r.user_id == owner), None))
        ]
        for row in rows:
            card = cards.get(row.user_id)
            if row.kind != "owner" and card is not None and card.live:
                members.append((card, row))
        return members

    @staticmethod
    def _tile(card: AccountCard, member: HouseholdMember | None) -> dict[str, Any]:
        return {
            "id": card.id,
            "display_name": card.display_name,
            "kind": member.kind if member is not None else "owner",
            "color": member.color if member is not None else color_for(None, 0),
            "has_avatar": card.has_avatar,
            "has_pin": member is not None and member.pin_hash is not None,
        }

    async def state(self, principal: Principal) -> dict[str, Any]:
        """For the « Who's there? » picker: the household's members, who is active, whether to choose."""
        owner = household_of(principal)
        members = await self._members(owner)
        chosen = await self.accounts().chosen(principal.session_id) if principal.session_id else True
        tiles = []
        for card, member in members:
            tile = self._tile(card, member)
            # entering a protected member asks its PIN, whoever comes from (the master too)
            tile["needs_pin"] = tile["has_pin"] and card.id != principal.user_id
            tiles.append(tile)
        return {
            "enabled": True,
            "made": await self.exists(principal.user_id) if principal.user_id else False,  # issue 445
            "owner_id": owner,
            "active_id": principal.user_id,
            "must_choose": len(tiles) > 1 and not chosen,
            "members": tiles,
        }

    async def switch(self, principal: Principal, target: UUID, pin: str | None) -> dict[str, Any]:
        owner = household_of(principal)
        if principal.session_id is None:
            raise Forbidden("Profiles are used from a signed-in browser.", code="household.no_session")
        async with self.database.session() as session:
            member = await session.get(HouseholdMember, target)
        belongs = target == owner or (
            member is not None and member.owner_id == owner and member.kind != "owner"
        )
        card = (await self.accounts().cards([target])).get(target)
        if not belongs or card is None or not card.live:
            raise NotFound("This profile does not exist.", code="household.member_not_found")
        if target != principal.user_id and member is not None and member.pin_hash is not None:
            await self.accounts().verify_pin(target, member.pin_hash, pin or "")
        await self.accounts().act(principal.session_id, owner, None if target == owner else target)
        log.info("household profile switched", extra={"fields": {"to_owner": target == owner}})
        return {"active_id": target}

    # --- the household page --------------------------------------------------------------------------
    async def _local_today(self) -> date:
        """The portal's day (its economy's time zone), as the screen time counts it."""
        zone = ZoneInfo("UTC")
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                zone = ZoneInfo(str((await providers[0].provider.get("economy.timezone")).value or "UTC"))
        except Exception:  # noqa: S110 — the day falls back to UTC's
            pass
        return self.now().astimezone(zone).date()

    async def give_minutes(self, principal: Principal, profile: UUID, minutes: int) -> None:
        """Issue 432: minutes of screen time more, today only (added to what was given today already)."""
        owner = self._manager(principal)
        if minutes not in EXTRA_MINUTES:
            raise Conflict("Choose 15, 30, 60 or 120 minutes.", code="household.invalid_minutes")
        today = await self._local_today()
        async with self.database.unit_of_work() as uow:
            member = await self._profile(uow.session, owner, profile)
            already = member.bonus_minutes if member.bonus_day == today else 0
            member.bonus_minutes, member.bonus_day = min(already + minutes, 24 * 60), today
            member.updated_at = self.now()
            await self._audit(
                uow.session, "household.minutes_given", principal, profile, {"minutes": minutes}
            )
        self._restrictions.pop(profile, None)

    async def free(self, principal: Principal, profile: UUID, minutes: int | None) -> None:
        """Issue 432: no limits for a while (``minutes``; ``None``: the limits back now)."""
        owner = self._manager(principal)
        if minutes is not None and not 15 <= minutes <= 24 * 60:
            raise Conflict("From 15 minutes to a day.", code="household.invalid_minutes")
        async with self.database.unit_of_work() as uow:
            member = await self._profile(uow.session, owner, profile)
            member.free_until = self.now() + timedelta(minutes=minutes) if minutes is not None else None
            member.updated_at = self.now()
            await self._audit(uow.session, "household.freed", principal, profile, {"minutes": minutes})
        self._restrictions.pop(profile, None)

    async def overview(self, principal: Principal) -> dict[str, Any]:
        """Every household member sees the household: its wallet (the master's balances, which hold every
        profile's earnings) and each member's figures; the restrictions to the master and to the profile."""
        owner = household_of(principal)
        limit = await self.limit()
        manager = principal.profile_of is None
        today = self.now().date()
        tiles = []
        for card, member in await self._members(owner):
            tile = self._tile(card, member)
            tile["progress"] = await self._progress(card.id)
            tile["community_visible"] = member.community_visible if member is not None else True
            if member is not None and member.kind != "owner" and (manager or card.id == principal.user_id):
                settings = parse(member.restrictions)
                tile["restrictions"] = settings.model_dump(mode="json")
                tile["age"] = settings.age(today)
                tile["effective_age"] = settings.effective_age(today)
                local = await self._local_today()
                tile["bonus_minutes"] = member.bonus_minutes if member.bonus_day == local else 0
                free = member.free_until if member.free_until and member.free_until > self.now() else None
                tile["free_until"] = free
            tiles.append(tile)
        return {
            "enabled": True,
            "owner_id": owner,
            "me": principal.user_id,
            "can_manage": manager,
            "max_profiles": limit,
            "palette": list(COLORS),
            "totals": tiles[0]["progress"] if tiles else None,
            "economy": await self.economy_of(owner),  # issue 443
            "members": tiles,
        }

    async def _progress(self, user: UUID) -> dict[str, int]:
        empty = {"xp": 0, "level": 0, "coins": 0, "contribution": 0}
        providers = self.capabilities.system_providers(PROGRESSION)
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

    async def _profile(self, session: AsyncSession, owner: UUID, profile: UUID) -> HouseholdMember:
        member = await session.get(HouseholdMember, profile, with_for_update=True)
        if member is None or member.owner_id != owner or member.kind == "owner":
            raise NotFound("This profile does not exist.", code="household.member_not_found")
        card = (await self.accounts().cards([profile])).get(profile)
        if card is None or not card.live:
            raise NotFound("This profile does not exist.", code="household.member_not_found")
        return member

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
        limit = await self.limit()
        if kind not in PROFILE_KINDS:
            raise Conflict("Choose standard, child or custom.", code="household.invalid_kind")
        pin_hash = await self.accounts().hash_pin(check_pin(pin)) if pin else None
        existing = await self.profiles_of(owner)
        live = [c for c in (await self.accounts().cards(list(existing))).values() if c.live]
        if len(live) >= limit:
            raise ProfileLimit(f"An account holds at most {limit} profiles.", extensions={"limit": limit})
        user = await self.accounts().create(display_name, principal)
        now = self.now()
        async with self.database.unit_of_work() as uow:
            await self._owner_row(uow.session, owner, now)
            position = len(existing) + 1
            restrictions, visible = preset(kind)
            uow.session.add(
                HouseholdMember(
                    user_id=user,
                    owner_id=owner,
                    kind=kind,
                    color=color_for(color, position),
                    position=position,
                    pin_hash=pin_hash,
                    community_visible=visible,
                    restrictions=restrictions.model_dump(mode="json"),
                    created_at=now,
                    updated_at=now,
                )
            )
            await self._audit(uow.session, "household.profile_created", principal, user, {"kind": kind})
        self._owners[user] = owner
        self.forget(user)
        return {"id": user}

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
        async with self.database.unit_of_work() as uow:
            member = await self._profile(uow.session, owner, profile)
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
            member.updated_at = self.now()
            await self._audit(
                uow.session,
                "household.profile_changed",
                principal,
                profile,
                {"kind": member.kind, "restrictions": member.restrictions},
            )
        if display_name is not None:
            await self.accounts().rename(profile, display_name)
        self.forget(profile)

    async def set_pin(
        self, principal: Principal, member_id: UUID, pin: str | None, current: str | None = None
    ) -> None:
        """The master sets or removes any member's PIN (its own included); a profile, its own — giving the
        one it replaces."""
        owner = household_of(principal)
        if principal.profile_of is not None and member_id != principal.user_id:
            raise OwnerOnly("Only the account's master changes another profile's PIN.")
        pin_hash = await self.accounts().hash_pin(check_pin(pin)) if pin else None
        async with self.database.session() as session:
            known = await session.get(HouseholdMember, member_id)
        if principal.profile_of is not None and known is not None and known.pin_hash is not None:
            await self.accounts().verify_pin(member_id, known.pin_hash, current or "")
        now = self.now()
        async with self.database.unit_of_work() as uow:
            if member_id == owner:
                member = await self._owner_row(uow.session, owner, now)
            else:
                member = await self._profile(uow.session, owner, member_id)
            member.pin_hash = pin_hash
            member.updated_at = now
            await self._audit(
                uow.session, "household.pin_changed", principal, member_id, {"set": pin_hash is not None}
            )

    async def remove(self, principal: Principal, profile: UUID) -> None:
        """The profile follows an account's deletion (at once); every browser using it is signed out."""
        owner = self._manager(principal)
        async with self.database.session() as session:
            await self._profile(session, owner, profile)
        await self.accounts().remove(profile, principal)
        async with self.database.unit_of_work() as uow:  # issue 445: no longer one of its household's
            row = await uow.session.get(HouseholdMember, profile, with_for_update=True)
            if row is not None:
                await uow.session.delete(row)
            # issue 450: nor its access requests (unnamed, they waited for its master)
            await uow.session.execute(delete(AccessRequest).where(AccessRequest.profile_id == profile))
        self.forget(profile)

    # --- supervision ---------------------------------------------------------------------------------
    async def activity(self, principal: Principal, profile: UUID) -> dict[str, Any]:
        """What a profile earned and spent lately, and its access requests — for its master (and itself)."""
        owner = household_of(principal)
        if principal.profile_of is not None and profile != principal.user_id:
            raise OwnerOnly("Only the account's master reads its profiles' activity.")
        async with self.database.session() as session:
            member = await session.get(HouseholdMember, profile)
        if member is None or member.owner_id != owner or member.kind == "owner":
            raise NotFound("This profile does not exist.", code="household.member_not_found")
        card = (await self.accounts().cards([profile])).get(profile)
        economy: list[dict[str, Any]] = []
        providers = self.capabilities.system_providers(ECONOMY)
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
        return {
            "last_seen_at": card.last_seen_at if card else None,
            "economy": economy,
            "requests": await self.requests(principal, profile),
        }

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
        async with self.database.session() as session:
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(
                            AccessRequest.status != "pending", AccessRequest.created_at.desc()
                        ).limit(60)
                    )
                ).all()
            )
        cards = await self.accounts().cards(list({row.profile_id for row in rows}))
        names = {user: card.display_name for user, card in cards.items()}
        return [self._request(row, names) for row in rows]

    async def ask(
        self, principal: Principal, *, kind: str, ref: str, title: str, rating: str | None, note: str | None
    ) -> dict[str, Any]:
        owner = household_of(principal)
        if principal.profile_of is None or principal.user_id is None:
            raise Forbidden("Only a profile asks its master for access.", code="household.not_a_profile")
        restrictions = await self.restrictions_of(principal.user_id)
        if restrictions is not None and not restrictions.requests:
            raise Forbidden("Your profile cannot ask for access.", code="household.requests_off")
        async with self.database.unit_of_work() as uow:
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
                created_at=self.now(),
            )
            uow.session.add(row)
            await uow.session.flush()
        card = (await self.accounts().cards([principal.user_id])).get(principal.user_id)
        await self._notify(
            owner,
            "household:notify.request",
            {
                # #431: the detailed e-mail — who asks, for what, its rating, their words
                "profile": card.display_name if card else "",
                "title": row.title,
                "rating": f"{row.rating}+" if row.rating and row.rating.isdigit() else (row.rating or ""),
                "quote": row.note or "",
            },
            f"household:request:{row.id}",
            "/household/requests",
        )
        return {"id": row.id, "status": "pending", "created": True}

    async def decide(self, principal: Principal, request: UUID, *, approve: bool, days: int | None) -> None:
        owner = self._manager(principal)
        now = self.now()
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(AccessRequest, request, with_for_update=True)
            if row is None or row.owner_id != owner:
                raise NotFound("This request does not exist.", code="household.request_not_found")
            if row.status != "pending":
                raise Conflict("This request was already answered.", code="household.request_answered")
            row.status = "approved" if approve else "denied"
            row.decided_at = now
            row.expires_at = now + timedelta(days=days) if approve and days else None
            await self._audit(
                uow.session,
                "household.access_decided",
                principal,
                row.profile_id,
                {"kind": row.kind, "ref": row.subject_ref, "approved": approve, "days": days},
            )
        await self._notify(
            row.profile_id,
            f"household:notify.{row.status}",
            {"title": row.title, "days": days or 0, "until": days or 0},
            f"household:decision:{row.id}",
            f"/media/{row.subject_ref}" if row.kind == "media" else "/household",
        )

    async def waiting(self, owner: UUID) -> int:
        async with self.database.session() as session:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(AccessRequest)
                    .where(AccessRequest.owner_id == owner, AccessRequest.status == "pending")
                )
                or 0
            )

    async def _notify(self, user: UUID, template: str, params: dict[str, Any], dedup: str, url: str) -> None:
        try:
            providers = self.capabilities.system_providers(NOTIFY)
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


class HouseholdAttention:
    """``shell.attention``: the access requests waiting for a household's master (« My household » badge)."""

    def __init__(self, service: HouseholdService) -> None:
        self.service = service

    async def counts(self, principal: Principal) -> dict[str, int]:
        if principal.user_id is None or principal.profile_of is not None or principal.channel != "user":
            return {}
        waiting = await self.service.waiting(principal.user_id)
        return {ATTENTION_ENTRY: waiting} if waiting else {}
