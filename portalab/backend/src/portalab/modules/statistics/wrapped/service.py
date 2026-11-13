"""Wrapped (T030; R9): admin-defined recaps (ordered statistics over a month, quarter or year) generated
into **immutable** snapshots — per user (personal data, owner-only, erased with the account) and for the
community (cohort thresholds apply). Each snapshot is computed through the provider *as the user*, so
permissions and unlocks hold; a failure for one user never blocks the others. Delivery goes through the
``notifications.send`` port (10) when present; the in-app page always works."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, select

from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import Period, StatResult, SubjectRef
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.event_port import SubjectRef as EventSubject
from portalab.core.time import Clock, utc_now
from portalab.modules.statistics.models import Bucket, WrappedDefinition, WrappedSnapshot
from portalab.modules.statistics.observability import log
from portalab.modules.statistics.period.resolver import local_day, resolve, zone
from portalab.modules.statistics.provider.provider import Provider


class WrappedNotFound(NotFound):
    default_code = "statistics.wrapped_not_found"
    default_title = "Recap not found"


def serialize(result: StatResult) -> dict[str, Any]:
    data = asdict(result)
    for name in ("as_of",):
        if data.get(name) is not None:
            data[name] = data[name].isoformat()
    for name in ("period_start", "period_end"):
        if data.get(name) is not None:
            data[name] = data[name].isoformat()
    return data


def last_completed(kind: str, today: date) -> tuple[date, date]:
    """The most recent fully elapsed month/quarter/year before ``today``."""
    probe = {"month": today.replace(day=1) - timedelta(days=1)}.get(kind)
    if kind == "quarter":
        start_this = date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)
        probe = start_this - timedelta(days=1)
    elif kind == "year":
        probe = date(today.year - 1, 12, 31)
    assert probe is not None
    return resolve(Period(kind), today=probe)  # type: ignore[arg-type]


class WrappedService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        provider: Provider,
        timezone: Callable[[], str],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.provider = provider
        self.timezone = timezone
        self.clock = clock

    async def save_definition(
        self, key: str, period_kind: str, stat_keys: Sequence[str], status: str = "active"
    ) -> None:
        if (
            period_kind not in ("month", "quarter", "year")
            or not stat_keys
            or status not in ("draft", "active", "retired")
        ):
            raise ValidationFailed("Invalid recap definition.", code="statistics.invalid_definition")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(WrappedDefinition, key, with_for_update=True)
            if row is None:
                uow.session.add(
                    WrappedDefinition(
                        key=key,
                        period_kind=period_kind,
                        stat_keys=list(stat_keys),
                        status=status,
                        version=1,
                        updated_at=now,
                    )
                )
            else:
                row.period_kind, row.stat_keys, row.status = period_kind, list(stat_keys), status
                row.version, row.updated_at = row.version + 1, now

    async def definitions(self) -> list[WrappedDefinition]:
        async with self.database.session() as session:
            return list(
                (await session.execute(select(WrappedDefinition).order_by(WrappedDefinition.key))).scalars()
            )

    async def generate(self, key: str | None = None) -> int:
        """Snapshots for the last completed period of every active recap (idempotent per subject/period)."""
        today = local_day(utc_now(self.clock), zone(self.timezone()))
        made = 0
        for definition in await self.definitions():
            if definition.status != "active" or (key is not None and definition.key != key):
                continue
            start, end = last_completed(definition.period_kind, today)
            made += await self._community(definition, start, end)
            for user in await self._contributors(definition, start, end):
                try:
                    made += await self._personal(definition, user, start, end)
                except Exception:
                    log.warning("recap generation failed for one user", extra={"recap": definition.key})
        return made

    async def _contributors(self, definition: WrappedDefinition, start: date, end: date) -> list[UUID]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Bucket.scope_id)
                .where(
                    Bucket.stat_key.in_(definition.stat_keys),
                    Bucket.scope_type == "personal",
                    Bucket.bucket_day.between(start, end),
                )
                .distinct()
            )
            return [row[0] for row in rows]

    async def _exists(
        self, definition: WrappedDefinition, start: date, scope: str, user: UUID | None
    ) -> bool:
        async with self.database.session() as session:
            found = await session.scalar(
                select(WrappedSnapshot.id).where(
                    and_(
                        WrappedSnapshot.wrapped_key == definition.key,
                        WrappedSnapshot.period_start == start,
                        WrappedSnapshot.subject_scope == scope,
                        WrappedSnapshot.user_id.is_(None)
                        if user is None
                        else WrappedSnapshot.user_id == user,
                    )
                )
            )
            return found is not None

    async def _store(
        self,
        definition: WrappedDefinition,
        start: date,
        end: date,
        scope: str,
        user: UUID | None,
        results: list[StatResult],
    ) -> UUID:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = WrappedSnapshot(
                wrapped_key=definition.key,
                period_start=start,
                period_end=end,
                subject_scope=scope,
                user_id=user,
                payload={"version": definition.version, "stats": [serialize(r) for r in results]},
                generated_at=now,
            )
            uow.session.add(row)
            await uow.session.flush()
            subject = EventSubject("user", str(user)) if user else None
            await self.events.publish(
                uow.session,
                "statistics.wrapped_generated",
                {"recap": definition.key, "period_start": start.isoformat(), "scope": scope},
                occurred_at=now,
                subject=subject,
                source="statistics",
                dedup_key=f"statistics.wrapped:{definition.key}:{start.isoformat()}:{user or 'community'}",
            )
            return row.id

    async def _personal(self, definition: WrappedDefinition, user: UUID, start: date, end: date) -> int:
        if await self._exists(definition, start, "user", user):
            return 0
        viewer = Principal(user_id=user)
        results = []
        for stat_key in definition.stat_keys:
            try:
                results.append(
                    await self.provider.get(
                        stat_key,
                        viewer=viewer,
                        subject=SubjectRef("user", user),
                        period=Period("custom", start=start, end=end),
                    )
                )
            except Exception:
                log.info("statistic left out of a recap", extra={"stat": stat_key})
                continue  # unknown, forbidden or failing statistics are simply left out of the recap
        if not results:
            return 0
        snapshot = await self._store(definition, start, end, "user", user, results)
        await self._deliver(user, definition, snapshot, start, end)
        return 1

    async def _community(self, definition: WrappedDefinition, start: date, end: date) -> int:
        if await self._exists(definition, start, "community", None):
            return 0
        results = []
        for stat_key in definition.stat_keys:
            active = await self.provider.definitions.get_active(stat_key)
            if active is None or active.definition.scope == "personal":
                continue
            try:
                results.append(await self.provider.community(stat_key, active, start, end))
            except Exception:
                log.info("statistic left out of a community recap", extra={"stat": stat_key})
                continue
        if not results:
            return 0
        await self._store(definition, start, end, "community", None, results)
        return 1

    async def _deliver(
        self, user: UUID, definition: WrappedDefinition, snapshot: UUID, start: date, end: date
    ) -> None:
        try:
            providers = self.capabilities.system_providers(NOTIFY)
        except Exception:
            return
        if not providers:
            return
        try:
            await asyncio.wait_for(
                providers[0].provider.send(
                    CommunicationRequest(
                        category="statistics.wrapped",
                        template_key="statistics:wrapped.ready",
                        audience=Users((user,)),
                        dedup_key=f"statistics.wrapped:{snapshot}",
                        # issue 398: the period it covers, never the definition's technical key
                        params={
                            "period": definition.period_kind,
                            "start_at": start.isoformat(),
                            "end_at": end.isoformat(),
                            "count": len(definition.stat_keys),
                        },
                        source="module",
                        action_url=f"/statistics/wrapped/{snapshot}",
                    )
                ),
                timeout=5,
            )
        except Exception:
            log.warning("recap notification not sent")

    async def mine(self, user: UUID) -> list[WrappedSnapshot]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(WrappedSnapshot)
                .where(WrappedSnapshot.user_id == user)
                .order_by(WrappedSnapshot.period_start.desc())
            )
            return list(rows.scalars())

    async def one(self, user: UUID, snapshot_id: UUID) -> WrappedSnapshot:
        async with self.database.session() as session:
            row = await session.get(WrappedSnapshot, snapshot_id)
            if row is None or row.user_id != user:
                raise WrappedNotFound("This recap does not exist.")
            return row

    async def community(self, period_start: date) -> list[WrappedSnapshot]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(WrappedSnapshot).where(
                    WrappedSnapshot.subject_scope == "community", WrappedSnapshot.period_start == period_start
                )
            )
            return list(rows.scalars())

    async def erase(self, user: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(WrappedSnapshot).where(WrappedSnapshot.user_id == user))
