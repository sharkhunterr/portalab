"""Retention engine (T027; FR-018/019, R4/R5): applies the configured windows to the registered targets.

Each target runs in its own transaction and records a ``privacy.retention_runs`` row (append-only);
a failing target never blocks the others. ``integrity_necessary`` targets are never touched; append-only
stores are only thinned by dropping whole partitions. Deleting or anonymizing old rows can only reduce what
is visible: nothing is ever made public.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Table, column, delete, table, text

from portalab.capabilities.retention import RetentionRegistry, RetentionTarget, default_retention_targets
from portalab.core.db import Database, all_metadata
from portalab.core.event_port import EventPublisher
from portalab.core.partitions import drop_month_partitions_before
from portalab.core.time import Clock, utc_now
from portalab.core.tombstone import scrub
from portalab.modules.privacy.models import RetentionRun
from portalab.modules.privacy.observability import log, metrics
from portalab.modules.privacy.settings import PrivacyConfig

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class TargetOutcome:
    target: str
    status: str
    rows: int
    cutoff: datetime | None


def _split(name: str) -> tuple[str, str]:
    schema, table_name = name.split(".", 1)
    if not (_IDENT.fullmatch(schema) and _IDENT.fullmatch(table_name)):
        raise ValueError(f"invalid table {name!r}")
    return schema, table_name


def _mapped_table(name: str) -> Table | None:
    for metadata in all_metadata():
        found = metadata.tables.get(name)
        if found is not None:
            return found
    return None


def months_before(now: datetime, months: int) -> datetime:
    year, month = now.year, now.month - months
    while month <= 0:
        month += 12
        year -= 1
    return now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


class RetentionEngine:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        *,
        registry: RetentionRegistry = default_retention_targets,
        config: PrivacyConfig | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.registry = registry
        self.config = config or PrivacyConfig()
        self.clock = clock

    def cutoff_for(self, target: RetentionTarget, now: datetime) -> datetime | None:
        if target.window is not None:
            window = target.window()
            return now - window if window else None
        if target.action == "drop_partition" and target.data_class == "audit":
            months = self.config.audit_retention_months
            return months_before(now, months) if months else None
        days = self.config.retention_days.get(target.data_class)
        return now - timedelta(days=days) if days else None

    async def run(self) -> list[TargetOutcome]:
        now = utc_now(self.clock)
        outcomes = []
        for target in self.registry.all():
            outcomes.append(await self._run_target(target, now))
        return outcomes

    async def _run_target(self, target: RetentionTarget, now: datetime) -> TargetOutcome:
        if target.integrity_necessary and target.action != "drop_partition":
            return TargetOutcome(target.name, "skipped", 0, None)
        cutoff = self.cutoff_for(target, now)
        if cutoff is None:
            return TargetOutcome(target.name, "skipped", 0, None)
        status, rows, error = "applied", 0, None
        try:
            async with self.database.unit_of_work() as uow:
                rows = await self._apply(uow.session, target, cutoff)
                await self.events.publish(
                    uow.session,
                    "privacy.retention_applied",
                    {"target": target.name, "action": target.action, "rows": rows},
                    occurred_at=now,
                    source="privacy",
                    dedup_key=f"retention:{target.name}:{now.strftime('%Y%m%dT%H%M%S')}",
                )
        except Exception as exc:
            status, rows, error = "failed", 0, type(exc).__name__
            log.warning("retention target failed", extra={"fields": {"target": target.name, "error": error}})
        async with self.database.unit_of_work() as uow:
            uow.session.add(
                RetentionRun(
                    target=target.name,
                    data_class=target.data_class,
                    action=target.action,
                    rows_affected=rows,
                    cutoff=cutoff,
                    run_at=now,
                    status=status,
                    error=error,
                )
            )
        metrics.increment(f"privacy.retention.{status}")
        metrics.increment("privacy.retention.rows", rows)
        return TargetOutcome(target.name, status, rows, cutoff)

    async def _apply(self, session: Any, target: RetentionTarget, cutoff: datetime) -> int:
        schema, table_name = _split(target.table)
        if not _IDENT.fullmatch(target.timestamp_column):
            raise ValueError("invalid timestamp column")
        if target.action == "drop_partition":
            return len(await drop_month_partitions_before(session, schema, table_name, cutoff))
        if target.action == "delete":
            clause = table(table_name, column(target.timestamp_column), schema=schema)
            condition = clause.c[target.timestamp_column] < cutoff
            if target.extra_condition:
                condition = condition & text(target.extra_condition)  # owner-written constant SQL
            result = await session.execute(delete(clause).where(condition))
            return int(getattr(result, "rowcount", 0) or 0)
        if target.action == "anonymize":
            mapped = _mapped_table(target.table)
            if mapped is None:
                raise ValueError(f"{target.table} is not a mapped table")
            return await scrub(session, mapped, where=mapped.c[target.timestamp_column] < cutoff)
        raise NotImplementedError(f"action {target.action!r} needs an owner-provided aggregator")
