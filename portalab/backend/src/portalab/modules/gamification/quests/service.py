"""Quests, daily objectives and challenges (T039; FR-008..010, R11).

Definitions are versioned (own ones, plus campaign-scoped quests from ``DefinitionSource`` providers that
offer ``quests(at)`` while the campaign is active — 014). For each event, inside the reward pipeline's
per-user transaction, every open quest whose steps count that event type advances the user's progress
for the event's **period** (computed from ``occurred_at`` in ``economy.timezone``). When all steps are met
the quest completes **once per (user, quest, period)**: rewards go through the ledger (idempotency
``quest:<user>:<key>:<period>:<value>``, ``source_kind`` = quest|daily|challenge) and ``quest.completed`` is
emitted with the same dedup. Redelivered events never reach here (the pipeline's applied-event marker)."""

import asyncio
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.economy import DEFINITION_SOURCES
from portalab.capabilities.events import Envelope
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter
from portalab.modules.gamification.models import Quest, QuestProgress
from portalab.modules.gamification.notify import Note
from portalab.modules.gamification.observability import log, metrics
from portalab.modules.gamification.quests.definition import QuestDefinition, parse_quest
from portalab.modules.gamification.quests.periods import period_key
from portalab.modules.gamification.rules.definition import matches

CACHE_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class QuestVersion:
    key: str
    version: int
    definition: QuestDefinition
    effective_from: datetime
    ends_at: datetime | None = None
    source_ref: str = ""

    def open_at(self, at: datetime) -> bool:
        return (
            self.effective_from <= at
            and (self.ends_at is None or at < self.ends_at)
            and self.definition.open_at(at)
        )


class QuestNotFound(NotFound):
    default_code = "economy.quest_not_found"
    default_title = "Quest not found"


class Quests:
    def __init__(
        self,
        database: Database,
        writer: LedgerWriter,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.writer = writer
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.config = config
        self.clock = clock
        self._own: tuple[float, list[QuestVersion]] | None = None

    # --- definitions -------------------------------------------------------------------------------------
    async def ensure_discovery(self) -> int:
        """027: the discovery missions exist on a fresh portal (a key once used is never created again)."""
        from portalab.modules.gamification.quests.discovery import DISCOVERY

        made = 0
        for key, raw in DISCOVERY.items():
            async with self.database.session() as session:
                if await session.scalar(select(Quest.key).where(Quest.key == key).limit(1)) is not None:
                    continue
            await self.save(Principal(channel="system"), key, raw)
            made += 1
        return made

    async def save(self, actor: Principal, key: str, raw: Mapping[str, Any]) -> Quest:
        definition = parse_quest(raw)
        async with self.database.unit_of_work() as uow:
            current = await uow.session.scalar(select(func.max(Quest.version)).where(Quest.key == key))
            row = Quest(
                key=key,
                version=int(current or 0) + 1,
                kind=definition.kind,
                status="active",
                effective_from=utc_now(self.clock),
                definition=definition.model_dump(mode="json"),
            )
            uow.session.add(row)
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="economy.quest_saved",
                    actor=actor,
                    resource=ResourceRef("quest", key),
                    decision="allow",
                    context={"version": row.version, "kind": row.kind},
                    sensitive=True,
                ),
            )
        self._own = None
        return row

    async def retire(self, actor: Principal, key: str) -> None:
        async with self.database.unit_of_work() as uow:
            rows = list(
                (await uow.session.execute(select(Quest).where(Quest.key == key).with_for_update())).scalars()
            )
            if not rows:
                raise QuestNotFound("This quest does not exist.")
            for row in rows:
                row.status = "retired"
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="economy.quest_retired",
                    actor=actor,
                    resource=ResourceRef("quest", key),
                    decision="allow",
                    sensitive=True,
                ),
            )
        self._own = None

    async def _own_definitions(self) -> list[QuestVersion]:
        if self._own and time.monotonic() - self._own[0] < CACHE_SECONDS:
            return self._own[1]
        async with self.database.session() as session:
            latest = select(Quest.key, func.max(Quest.version).label("v")).group_by(Quest.key).subquery()
            rows = (
                await session.execute(
                    select(Quest)
                    .join(latest, (Quest.key == latest.c.key) & (Quest.version == latest.c.v))
                    .where(Quest.status == "active")
                )
            ).scalars()
            found = [
                QuestVersion(r.key, r.version, QuestDefinition.model_validate(r.definition), r.effective_from)
                for r in rows
            ]
        self._own = (time.monotonic(), found)
        return found

    async def definitions(self, at: datetime) -> list[QuestVersion]:
        found = [d for d in await self._own_definitions() if d.effective_from <= at]
        known = {d.key for d in found}
        try:
            sources = self.capabilities.system_providers(DEFINITION_SOURCES)
        except Exception:
            sources = []
        for registration in sources:
            quests = getattr(registration.provider, "quests", None)
            if quests is None:
                continue
            try:
                extra = await asyncio.wait_for(quests(at), 2)
            except Exception:
                log.warning("quest definition source unavailable")
                continue
            for item in extra:
                if item.key in known:
                    continue
                try:
                    definition = parse_quest(item.definition)
                except Exception:
                    log.warning("invalid external quest ignored")
                    continue
                found.append(
                    QuestVersion(
                        item.key, item.version, definition, item.effective_from, item.ends_at, item.source_ref
                    )
                )
                known.add(item.key)
        return sorted(found, key=lambda d: d.key)

    async def tracks(self, event_type: str, at: datetime) -> bool:
        return any(
            step.event_type == event_type
            for quest in await self.definitions(at)
            if quest.open_at(at)
            for step in quest.definition.steps
        )

    # --- evaluation --------------------------------------------------------------------------------------
    async def on_event(self, session: AsyncSession, user: UUID, envelope: Envelope) -> list[Note]:
        at = envelope.occurred_at
        notes: list[Note] = []
        timezone = self.config().timezone
        for quest in await self.definitions(at):
            if not quest.open_at(at):
                continue
            hits = [
                index
                for index, step in enumerate(quest.definition.steps)
                if step.event_type == envelope.type and matches(step.filter, envelope.payload)
            ]
            if not hits:
                continue
            period = period_key(quest.definition.period, at, timezone)
            notes.extend(await self._advance(session, user, quest, period, hits, at))
        return notes

    async def _advance(
        self,
        session: AsyncSession,
        user: UUID,
        quest: QuestVersion,
        period: str,
        hits: Sequence[int],
        at: datetime,
    ) -> list[Note]:
        steps = quest.definition.steps
        now = utc_now(self.clock)
        await session.execute(
            insert(QuestProgress)
            .values(
                user_id=user,
                quest_key=quest.key,
                period_key=period,
                version=quest.version,
                counts=[0] * len(steps),
                updated_at=now,
            )
            .on_conflict_do_nothing()
        )
        row = await session.get(QuestProgress, (user, quest.key, period), with_for_update=True)
        if row is None or row.completed_at is not None:
            return []
        counts = list(row.counts)[: len(steps)] + [0] * max(0, len(steps) - len(row.counts))
        if row.version != quest.version:
            counts, row.version = [0] * len(steps), quest.version
        for index in hits:
            counts[index] = min(counts[index] + 1, steps[index].count)
        row.counts, row.updated_at = counts, now
        if any(counts[i] < step.count for i, step in enumerate(steps)):
            return []
        row.completed_at = at
        return await self._complete(session, user, quest, period, at)

    async def _complete(
        self, session: AsyncSession, user: UUID, quest: QuestVersion, period: str, at: datetime
    ) -> list[Note]:
        notes = [
            Note(
                "quest",
                user,
                f"quest:{user}:{quest.key}:{period}",
                {"quest": quest.definition.label, "kind": quest.definition.kind},
            )
        ]
        for reward in quest.definition.rewards:
            recorded = await self.writer.record(
                session,
                Entry(
                    user_id=user,
                    value=reward.value,
                    delta=reward.amount,
                    kind="grant",
                    source_kind=quest.definition.kind,
                    source_ref=f"quest:{quest.key}:{period}",
                    idempotency_key=f"quest:{user}:{quest.key}:{period}:{reward.value}",
                    occurred_at=at,
                    base_amount=reward.amount,
                ),
            )
            if recorded.level_up:
                notes.append(
                    Note("level_up", user, f"level:{user}:{recorded.level_up}", {"level": recorded.level_up})
                )
        await self.events.publish(
            session,
            "quest.completed",
            {"quest": quest.key, "kind": quest.definition.kind, "period": period},
            occurred_at=at,
            actor=Principal(user_id=user, channel="system"),
            subject=SubjectRef("user", str(user)),
            dedup_key=f"quest.completed:{user}:{quest.key}:{period}",
        )
        metrics.increment(f"gamification.quests.completed.{quest.definition.kind}")
        return notes

    # --- reads -------------------------------------------------------------------------------------------
    async def mine(self, user: UUID, *, kinds: Sequence[str] | None = None) -> list[dict[str, Any]]:
        """The user's open quests for the current period, with step progress (own data only)."""
        now = utc_now(self.clock)
        timezone = self.config().timezone
        open_quests = [
            q
            for q in await self.definitions(now)
            if q.open_at(now) and (kinds is None or q.definition.kind in kinds)
        ]
        wanted = {(q.key, period_key(q.definition.period, now, timezone)) for q in open_quests}
        async with self.database.session() as session:
            rows = {
                (r.quest_key, r.period_key): r
                for r in (
                    await session.execute(select(QuestProgress).where(QuestProgress.user_id == user))
                ).scalars()
                if (r.quest_key, r.period_key) in wanted
            }
        out: list[dict[str, Any]] = []
        for quest in open_quests:
            period = period_key(quest.definition.period, now, timezone)
            row = rows.get((quest.key, period))
            counts = list(row.counts) if row and row.version == quest.version else []
            out.append(
                {
                    **self.describe(quest),
                    "period_key": period,
                    "completed_at": row.completed_at.isoformat() if row and row.completed_at else None,
                    "steps": [
                        {
                            "event_type": step.event_type,
                            "current": counts[i] if i < len(counts) else 0,
                            "target": step.count,
                        }
                        for i, step in enumerate(quest.definition.steps)
                    ],
                }
            )
        return out

    @staticmethod
    def describe(quest: QuestVersion) -> dict[str, Any]:
        definition = quest.definition
        return {
            "key": quest.key,
            "kind": definition.kind,
            "label": definition.label,
            "description": definition.description,
            "icon": definition.icon,
            "period": definition.period,
            "starts_at": definition.window.starts_at.isoformat() if definition.window else None,
            "ends_at": (
                definition.window.ends_at.isoformat()
                if definition.window
                else (quest.ends_at.isoformat() if quest.ends_at else None)
            ),
            "rewards": [r.model_dump() for r in definition.rewards],
        }

    async def catalog(self) -> list[dict[str, Any]]:
        now = utc_now(self.clock)
        return [self.describe(q) for q in await self.definitions(now) if q.open_at(now)]
