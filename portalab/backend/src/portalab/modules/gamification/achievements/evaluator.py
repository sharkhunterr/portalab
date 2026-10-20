"""Achievements (T026, T034): definitions (own versions + campaign-scoped ones from ``DefinitionSource``
providers while their window is open), counters for ``event_count`` criteria, evaluation and a **single**
unlock per user (unique constraint, safe under concurrent events) whose rewards go through the ledger
(``source_kind=achievement``) and which emits ``achievement.unlocked``."""

import asyncio
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.economy import DEFINITION_SOURCES
from portalab.capabilities.events import Envelope
from portalab.capabilities.identity_directory import CONTACT
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import PROVIDER as STATISTICS
from portalab.capabilities.statistics import SubjectRef as StatSubject
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.achievements.definition import (
    AchievementDefinition,
    EventCount,
    LevelAtLeast,
    StatisticAtLeast,
    ValueAtLeast,
    parse_achievement,
)
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter
from portalab.modules.gamification.models import Achievement, Balance, Counter, UserAchievement
from portalab.modules.gamification.notify import Note
from portalab.modules.gamification.observability import log, metrics
from portalab.modules.gamification.rules.definition import matches

CACHE_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class Definition:
    key: str
    version: int
    definition: AchievementDefinition
    effective_from: datetime
    ends_at: datetime | None = None
    source_ref: str = ""

    def counter(self, index: int) -> str:
        return f"{self.key}:{self.version}:{index}"


def rarity_of(share: float) -> str:
    """027 US9: rarity from the unlock share — common > 50 %, rare 20-50 %, epic 5-20 %, legendary < 5 %."""
    if share > 50:
        return "common"
    if share >= 20:
        return "rare"
    if share >= 5:
        return "epic"
    return "legendary"


class AchievementNotFound(NotFound):
    default_code = "economy.achievement_not_found"
    default_title = "Achievement not found"


class Achievements:
    def __init__(
        self,
        database: Database,
        writer: LedgerWriter,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.writer = writer
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.clock = clock
        self._own: tuple[float, list[Definition]] | None = None

    # --- definitions -------------------------------------------------------------------------------------
    async def save(self, actor: Principal, key: str, raw: Mapping[str, Any]) -> Achievement:
        definition = parse_achievement(raw)
        async with self.database.unit_of_work() as uow:
            current = await uow.session.scalar(
                select(func.max(Achievement.version)).where(Achievement.key == key)
            )
            row = Achievement(
                key=key,
                version=int(current or 0) + 1,
                status="active",
                effective_from=utc_now(self.clock),
                definition=definition.model_dump(),
            )
            uow.session.add(row)
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="economy.achievement_saved",
                    actor=actor,
                    resource=ResourceRef("achievement", key),
                    decision="allow",
                    context={"version": row.version},
                    sensitive=True,
                ),
            )
        self._own = None
        return row

    async def retire(self, actor: Principal, key: str) -> None:
        async with self.database.unit_of_work() as uow:
            rows = list(
                (
                    await uow.session.execute(
                        select(Achievement).where(Achievement.key == key).with_for_update()
                    )
                ).scalars()
            )
            if not rows:
                raise AchievementNotFound("This achievement does not exist.")
            for row in rows:
                row.status = "retired"
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="economy.achievement_retired",
                    actor=actor,
                    resource=ResourceRef("achievement", key),
                    decision="allow",
                    sensitive=True,
                ),
            )
        self._own = None

    async def _own_definitions(self) -> list[Definition]:
        if self._own and time.monotonic() - self._own[0] < CACHE_SECONDS:
            return self._own[1]
        async with self.database.session() as session:
            latest = (
                select(Achievement.key, func.max(Achievement.version).label("v"))
                .group_by(Achievement.key)
                .subquery()
            )
            rows = (
                await session.execute(
                    select(Achievement)
                    .join(latest, (Achievement.key == latest.c.key) & (Achievement.version == latest.c.v))
                    .where(Achievement.status == "active")
                )
            ).scalars()
            found = [
                Definition(
                    r.key, r.version, AchievementDefinition.model_validate(r.definition), r.effective_from
                )
                for r in rows
            ]
        self._own = (time.monotonic(), found)
        return found

    async def definitions(self, at: datetime) -> list[Definition]:
        found = [d for d in await self._own_definitions() if d.effective_from <= at]
        known = {d.key for d in found}
        try:
            sources = self.capabilities.system_providers(DEFINITION_SOURCES)
        except Exception:
            sources = []
        for registration in sources:
            try:
                extra = await asyncio.wait_for(registration.provider.achievements(at), 2)
            except Exception:
                log.warning("achievement definition source unavailable")
                continue
            for item in extra:
                if item.key in known or item.effective_from > at or (item.ends_at and item.ends_at <= at):
                    continue
                try:
                    definition = parse_achievement(item.definition)
                except Exception:
                    log.warning("invalid external achievement ignored")
                    continue
                found.append(
                    Definition(
                        item.key, item.version, definition, item.effective_from, item.ends_at, item.source_ref
                    )
                )
                known.add(item.key)
        return sorted(found, key=lambda d: d.key)

    async def tracks(self, event_type: str, at: datetime) -> bool:
        return any(
            isinstance(c, EventCount) and c.event_type == event_type
            for d in await self.definitions(at)
            for c in d.definition.criteria
        )

    # --- evaluation --------------------------------------------------------------------------------------
    async def unlocked(self, session: AsyncSession, user: UUID) -> set[str]:
        rows = await session.execute(
            select(UserAchievement.achievement_key).where(UserAchievement.user_id == user)
        )
        return set(rows.scalars())

    async def on_event(self, session: AsyncSession, user: UUID, envelope: Envelope) -> list[Note]:
        definitions = await self.definitions(envelope.occurred_at)
        done = await self.unlocked(session, user)
        now = utc_now(self.clock)
        for definition in definitions:
            if definition.key in done or envelope.occurred_at < definition.effective_from:
                continue
            for index, criterion in enumerate(definition.definition.criteria):
                if (
                    isinstance(criterion, EventCount)
                    and criterion.event_type == envelope.type
                    and matches(criterion.filter, envelope.payload)
                ):
                    statement = insert(Counter).values(
                        user_id=user, counter_key=definition.counter(index), value=1, updated_at=now
                    )
                    await session.execute(
                        statement.on_conflict_do_update(
                            index_elements=[Counter.user_id, Counter.counter_key],
                            set_={"value": Counter.value + 1, "updated_at": now},
                        )
                    )
        return await self.evaluate(session, user, envelope.occurred_at, definitions, done)

    async def evaluate(
        self,
        session: AsyncSession,
        user: UUID,
        at: datetime,
        definitions: Sequence[Definition] | None = None,
        done: set[str] | None = None,
    ) -> list[Note]:
        definitions = definitions if definitions is not None else await self.definitions(at)
        done = done if done is not None else await self.unlocked(session, user)
        notes: list[Note] = []
        for definition in definitions:
            if definition.key not in done and await self._satisfied(session, user, definition):
                notes.extend(await self.unlock(session, user, definition, at))
        return notes

    async def _satisfied(self, session: AsyncSession, user: UUID, definition: Definition) -> bool:
        for index, criterion in enumerate(definition.definition.criteria):
            if isinstance(criterion, EventCount):
                counter = await session.get(Counter, (user, definition.counter(index)))
                if counter is None or counter.value < criterion.count:
                    return False
            elif isinstance(criterion, LevelAtLeast):
                balance = await session.get(Balance, (user, "xp"))
                if balance is None or (balance.level or 1) < criterion.level:
                    return False
            elif isinstance(criterion, ValueAtLeast):
                balance = await session.get(Balance, (user, criterion.value))
                if balance is None or balance.amount < criterion.amount:
                    return False
            elif isinstance(criterion, StatisticAtLeast) and not await self._statistic(user, criterion):
                return False
        return True

    async def _statistic(self, user: UUID, criterion: StatisticAtLeast) -> bool:
        try:
            providers = self.capabilities.system_providers(STATISTICS)
            if not providers:
                return False
            result = await asyncio.wait_for(
                providers[0].provider.get(
                    criterion.statistic,
                    viewer=Principal(user_id=user),
                    subject=StatSubject("user", user),
                ),
                2,
            )
        except Exception:
            return False
        return result.state in ("available", "partial", "stale") and (result.value or 0) >= criterion.amount

    async def unlock(
        self, session: AsyncSession, user: UUID, definition: Definition, at: datetime
    ) -> list[Note]:
        inserted = (
            await session.execute(
                insert(UserAchievement)
                .values(
                    user_id=user,
                    achievement_key=definition.key,
                    version=definition.version,
                    unlocked_at=at,
                    transaction_ids=[],
                )
                .on_conflict_do_nothing(constraint="uq_user_achievements")
                .returning(UserAchievement.id)
            )
        ).scalar_one_or_none()
        if inserted is None:
            return []
        shown = definition.definition  # 027: the member reads its name and what it rewards, not its key
        # issue 175: what it gives, in its own notification (no second « you earned »)
        said: dict[str, Any] = {
            "achievement": shown.label,
            "description": shown.description,
            "xp": 0,
            "coins": 0,
            "contribution": 0,
        }
        notes = [
            Note(
                "achievement",
                user,
                f"achievement:{user}:{definition.key}",
                said,
                gifts=tuple(unlock.product for unlock in shown.unlocks),
            )
        ]
        ids: list[str] = []
        for reward in definition.definition.rewards:
            recorded = await self.writer.record(
                session,
                Entry(
                    user_id=user,
                    value=reward.value,
                    delta=reward.amount,
                    kind="grant",
                    source_kind="achievement",
                    source_ref=f"achievement:{definition.key}",
                    idempotency_key=f"achievement:{user}:{definition.key}:{reward.value}",
                    occurred_at=at,
                    base_amount=reward.amount,
                ),
            )
            ids.append(str(recorded.transaction.id))
            if reward.value in ("xp", "coins", "contribution") and not recorded.duplicate:
                said[reward.value] += int(recorded.transaction.delta)
            if recorded.level_up:
                notes.append(
                    Note("level_up", user, f"level:{user}:{recorded.level_up}", {"level": recorded.level_up})
                )
        row = await session.get(UserAchievement, inserted)
        if row is not None:
            row.transaction_ids = ids
        await self.events.publish(
            session,
            "achievement.unlocked",
            {"achievement": definition.key},
            occurred_at=at,
            actor=Principal(user_id=user, channel="system"),
            subject=SubjectRef("user", str(user)),
            dedup_key=f"achievement.unlocked:{user}:{definition.key}",
        )
        metrics.increment("gamification.achievements.unlocked")
        return notes

    async def unlock_by_key(self, session: AsyncSession, user: UUID, key: str, at: datetime) -> list[Note]:
        for definition in await self.definitions(at):
            if definition.key == key:
                return await self.unlock(session, user, definition, at)
        raise AchievementNotFound("This achievement does not exist.")

    async def unlock_shares(self) -> dict[str, float]:
        """027 US9: share (%) of active members who unlocked each achievement — aggregate, non-identifying."""
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(UserAchievement.achievement_key, func.count()).group_by(
                        UserAchievement.achievement_key
                    )
                )
            ).all()
            counts: dict[str, int] = {str(key): int(n) for key, n in rows}
            fallback = int(
                await session.scalar(select(func.count(func.distinct(UserAchievement.user_id)))) or 0
            )
        total = fallback
        providers = self.capabilities.system_providers(CONTACT)
        if providers:
            try:
                total = max(total, len(await providers[0].provider.active_user_ids()))
            except Exception:
                total = fallback
        return {key: round(100 * int(n) / total, 1) for key, n in counts.items()} if total else {}

    async def progress(self, user: UUID) -> list[dict[str, Any]]:
        """Own view: unlocked ones and progress of visible ones; hidden ones appear only once unlocked."""
        now = utc_now(self.clock)
        shares = await self.unlock_shares()
        async with self.database.session() as session:
            unlocked = {
                r.achievement_key: r
                for r in (
                    await session.execute(select(UserAchievement).where(UserAchievement.user_id == user))
                ).scalars()
            }
            counters = {
                c.counter_key: c.value
                for c in (await session.execute(select(Counter).where(Counter.user_id == user))).scalars()
            }
        out: list[dict[str, Any]] = []
        for definition in await self.definitions(now):
            row = unlocked.get(definition.key)
            share = shares.get(definition.key, 0.0)
            if definition.definition.hidden and row is None:
                out.append(
                    {
                        "key": definition.key,
                        "state": "hidden",
                        "unlock_share": share,
                        "rarity": rarity_of(share),
                    }
                )
                continue
            steps = [
                {"current": min(counters.get(definition.counter(i), 0), c.count), "target": c.count}
                for i, c in enumerate(definition.definition.criteria)
                if isinstance(c, EventCount)
            ]
            out.append(
                {
                    "key": definition.key,
                    "state": "unlocked" if row else "locked",
                    "label": definition.definition.label,
                    "description": definition.definition.description,
                    "icon": definition.definition.icon,
                    "category": definition.definition.category,
                    "unlock_share": share,
                    "rarity": rarity_of(share),
                    "unlocked_at": row.unlocked_at.isoformat() if row else None,
                    "progress": steps,
                    # 027: what it gives — Coins and co, and the cosmetics it unlocks
                    "rewards": [
                        {"value": r.value, "amount": r.amount} for r in definition.definition.rewards
                    ],
                    "unlocks": [u.model_dump() for u in definition.definition.unlocks],
                }
            )
        return out
