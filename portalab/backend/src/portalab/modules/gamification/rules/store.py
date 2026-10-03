"""Rule store and resolver (T014; R3): versions are append-only — a change is a new version, never an edit.
Publishing sets ``effective_from`` (now); the version **in force at an event's ``occurred_at``** decides the
grant; retiring stops a rule for later events. Every admin change is audited (sensitive)."""

import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from portalab.capabilities.events import EventTypeRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.models import RewardRule
from portalab.modules.gamification.rules.definition import RuleDefinition, parse_rule

CACHE_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class RuleVersion:
    key: str
    version: int
    definition: RuleDefinition
    effective_from: datetime
    retired_at: datetime | None


class RuleNotFound(NotFound):
    default_code = "economy.rule_not_found"
    default_title = "Rule not found"


class RuleStore:
    def __init__(
        self,
        database: Database,
        audit: AuditSink,
        events: EventPublisher,
        types: EventTypeRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.audit = audit
        self.events = events
        self.types = types
        self.clock = clock
        self._published: tuple[float, list[RuleVersion]] | None = None

    def invalidate(self) -> None:
        self._published = None

    async def _audit(self, session: Any, actor: Principal, action: str, key: str, version: int) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("reward_rule", key),
                decision="allow",
                context={"version": version},
                sensitive=True,
            ),
        )

    async def save(self, actor: Principal, key: str, raw: Mapping[str, Any]) -> RewardRule:
        rule = parse_rule(raw, self.types)
        async with self.database.unit_of_work() as uow:
            current = await uow.session.scalar(
                select(func.max(RewardRule.version)).where(RewardRule.key == key)
            )
            row = RewardRule(
                key=key,
                version=int(current or 0) + 1,
                status="draft",
                event_type=rule.event_type,
                definition=rule.model_dump(),
                created_by=actor.acting_for or actor.user_id,
                created_at=utc_now(self.clock),
            )
            uow.session.add(row)
            await self._audit(uow.session, actor, "economy.rule_saved", key, row.version)
            return row

    async def get(self, key: str, version: int | None = None) -> RewardRule:
        async with self.database.session() as session:
            statement = select(RewardRule).where(RewardRule.key == key)
            statement = (
                statement.where(RewardRule.version == version)
                if version
                else statement.order_by(RewardRule.version.desc()).limit(1)
            )
            row = (await session.execute(statement)).scalar_one_or_none()
        if row is None:
            raise RuleNotFound("This rule does not exist.")
        return row

    async def versions(self, key: str) -> list[RewardRule]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(RewardRule).where(RewardRule.key == key).order_by(RewardRule.version)
            )
            return list(rows.scalars())

    async def latest(self) -> list[RewardRule]:
        async with self.database.session() as session:
            latest = (
                select(RewardRule.key, func.max(RewardRule.version).label("v"))
                .group_by(RewardRule.key)
                .subquery()
            )
            rows = await session.execute(
                select(RewardRule)
                .join(latest, (RewardRule.key == latest.c.key) & (RewardRule.version == latest.c.v))
                .order_by(RewardRule.key)
            )
            return list(rows.scalars())

    async def publish(self, actor: Principal, key: str, version: int) -> RewardRule:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(RewardRule, (key, version), with_for_update=True)
            if row is None:
                raise RuleNotFound("This rule does not exist.")
            if row.status != "draft":
                raise Conflict("Only a draft can be published.", code="economy.rule_not_draft")
            parse_rule(row.definition, self.types)  # still valid against today's event registry
            row.status, row.effective_from = "active", now
            await self._audit(uow.session, actor, "economy.rule_published", key, version)
            await self.events.publish(
                uow.session,
                "economy.rule_published",
                {"rule": key, "version": version},
                occurred_at=now,
                actor=actor,
                dedup_key=f"economy.rule_published:{key}:{version}",
            )
        self.invalidate()
        return row

    async def retire(self, actor: Principal, key: str) -> RewardRule:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            rows = list(
                (
                    await uow.session.execute(
                        select(RewardRule)
                        .where(RewardRule.key == key, RewardRule.status == "active")
                        .with_for_update()
                    )
                ).scalars()
            )
            if not rows:
                raise RuleNotFound("This rule is not active.")
            for row in rows:
                row.status, row.retired_at = "retired", now
            await self._audit(uow.session, actor, "economy.rule_retired", key, max(r.version for r in rows))
        self.invalidate()
        return rows[-1]

    async def published(self) -> list[RuleVersion]:
        if self._published and time.monotonic() - self._published[0] < CACHE_SECONDS:
            return self._published[1]
        async with self.database.session() as session:
            rows = (
                await session.execute(select(RewardRule).where(RewardRule.effective_from.is_not(None)))
            ).scalars()
            versions = [
                RuleVersion(
                    r.key,
                    r.version,
                    RuleDefinition.model_validate(r.definition),
                    r.effective_from,
                    r.retired_at,
                )
                for r in rows
                if r.effective_from is not None
            ]
        self._published = (time.monotonic(), versions)
        return versions

    async def in_force(self, event_type: str, at: datetime) -> list[RuleVersion]:
        """Per rule key, the latest published version in force at ``at`` (effective and not yet retired)."""
        chosen: dict[str, RuleVersion] = {}
        for version in await self.published():
            if version.definition.event_type != event_type or version.effective_from > at:
                continue
            if version.retired_at is not None and version.retired_at <= at:
                continue
            best = chosen.get(version.key)
            if best is None or version.version > best.version:
                chosen[version.key] = version
        return [chosen[key] for key in sorted(chosen)]

    async def event_types(self) -> set[str]:
        return {v.definition.event_type for v in await self.published()}
