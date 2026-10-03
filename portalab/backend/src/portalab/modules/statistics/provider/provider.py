"""``StatisticsProvider`` (T013, T019, T024, T028; R5-R8, R10): the single authoritative read path. Every
consumer — the API, dashboard widgets, gamification, Wrapped, AI tools — gets the same value for the same
statistic, subject, period and filters, always bounded by the viewer:

1. the statistic is active and the viewer holds ``statistics.read`` + its own permission;
2. unlock conditions — locked ⇒ only a hint, **no bucket is read**;
3. privacy — another user's personal statistic needs that user's visibility (021); community values need
   ``min_cohort_size`` distinct contributors (else ``insufficient_data``), small cells merged/suppressed;
4. buckets of the definition lineage over the resolved period (bounded count), roll-up, trend versus the
   previous period of equal length;
5. honesty — source services down ⇒ ``partial``/``unavailable``; projection lagging beyond the threshold ⇒
   ``stale``; ``as_of`` always set.
"""

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select

from portalab.capabilities.events import STATS_CAPABILITY
from portalab.capabilities.health import SERVICE_STATE
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import CatalogEntry, Period, StatResult, StatState, SubjectRef
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import Forbidden, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.statistics.definitions.service import (
    ActiveDefinition,
    DefinitionService,
    UnknownStatistic,
)
from portalab.modules.statistics.models import COMMUNITY, Bucket, Member, ProjectionState
from portalab.modules.statistics.observability import metrics
from portalab.modules.statistics.period.resolver import local_day, previous, resolve, zone
from portalab.modules.statistics.permissions import STATISTICS_READ
from portalab.modules.statistics.privacy.guard import Cell, PrivacyGuard
from portalab.modules.statistics.projection.consumers import consumer_name
from portalab.modules.statistics.settings import StatisticsConfig
from portalab.modules.statistics.trend.calculator import trend
from portalab.modules.statistics.unlock.evaluator import UnlockEvaluator

DEFAULT_PERIOD = Period("last_n_days", days=30)


class StatisticForbidden(Forbidden):
    default_code = "statistics.forbidden"
    default_title = "Statistic not available to you"


class TooManyBuckets(ValidationFailed):
    default_code = "statistics.too_many_buckets"
    default_title = "Period too long"


class InvalidFilter(ValidationFailed):
    default_code = "statistics.invalid_filter"
    default_title = "Invalid statistic filter"


def _merge(kind: str) -> Callable[[float, float], float]:
    if kind == "min":
        return min
    if kind == "max":
        return max
    return lambda a, b: a + b


class Provider:
    def __init__(
        self,
        database: Database,
        definitions: DefinitionService,
        unlocks: UnlockEvaluator,
        guard: PrivacyGuard,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        config: Callable[[], StatisticsConfig],
        timezone: Callable[[], str],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.definitions = definitions
        self.unlocks = unlocks
        self.guard = guard
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.config = config
        self.timezone = timezone
        self.clock = clock

    def _port(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def _allowed(self, viewer: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(viewer, permission)
        except Exception:
            return False

    async def permitted(self, viewer: Principal, active: ActiveDefinition) -> bool:
        return await self._allowed(viewer, STATISTICS_READ) and await self._allowed(
            viewer, active.definition.required_permission
        )

    # --- catalog -------------------------------------------------------------------------------------
    async def catalog(self, viewer: Principal) -> Sequence[CatalogEntry]:
        user = viewer.acting_for or viewer.user_id
        out = []
        for active in await self.definitions.active():
            if not await self.permitted(viewer, active):
                continue
            d = active.definition
            locked, hint = await self.unlocks.locked(user, d)
            out.append(
                CatalogEntry(
                    d.key,
                    d.title_key,
                    d.description_key,
                    d.domain,
                    d.scope,
                    d.viz.type,
                    d.hideable,
                    locked,
                    hint,
                    d.period_options,
                )
            )
        return sorted(out, key=lambda e: (e.domain, e.key))

    # --- read ----------------------------------------------------------------------------------------
    async def get(
        self,
        stat_key: str,
        *,
        viewer: Principal,
        subject: SubjectRef | None = None,
        period: Period | None = None,
        filters: Mapping[str, str] | None = None,
    ) -> StatResult:
        active = await self.definitions.get_active(stat_key)
        if active is None:
            raise UnknownStatistic("This statistic does not exist.")
        if not await self.permitted(viewer, active):
            raise StatisticForbidden("You cannot see this statistic.")
        d = active.definition
        user = viewer.acting_for or viewer.user_id
        locked, hint = await self.unlocks.locked(user, d)
        if locked:
            metrics.increment("statistics.locked")
            return StatResult(stat_key, "locked", active.version, unlock_hint=hint)
        scope_id = COMMUNITY
        if d.scope == "personal":
            target = subject.id if subject is not None and subject.kind == "user" and subject.id else user
            if target is None:
                raise StatisticForbidden("A personal statistic needs a user.")
            if not await self.guard.subject_visible(viewer, target, stat_key):
                raise StatisticForbidden("This person's statistics are private.")
            scope_id = target
        config = self.config()
        today = local_day(utc_now(self.clock), zone(self.timezone()))
        start, end = resolve(
            period or DEFAULT_PERIOD, today=today, first_day_of_week=config.first_day_of_week
        )
        days = (end - start).days + 1
        if days * max(1, len(d.dimensions) + 1) > config.max_buckets_per_request:
            raise TooManyBuckets(
                "This period is too long for this statistic; choose a shorter one.",
                extensions={"max_days": config.max_buckets_per_request // max(1, len(d.dimensions) + 1)},
            )
        wanted = dict(filters or {})
        if any(name not in d.dimensions for name in wanted):
            raise InvalidFilter(
                "This statistic cannot be filtered that way.", extensions={"filters": sorted(wanted)}
            )
        current = await self._compute(active, scope_id, start, end, wanted)
        threshold = d.min_cohort_size or config.default_min_cohort_size
        people = current["contributors"] > 0 or current["events"] == 0  # events without actors involve no one
        if d.scope != "personal" and people and current["contributors"] < threshold:
            metrics.increment("statistics.insufficient_data")
            return StatResult(
                stat_key,
                "insufficient_data",
                active.version,
                as_of=await self._as_of(active),
                period_start=start,
                period_end=end,
            )
        before_start, before_end = previous(start, end)
        before = await self._compute(active, scope_id, before_start, before_end, wanted)
        before_ok = (
            d.scope == "personal" or before["contributors"] >= threshold or before["contributors"] == 0
        )
        state: StatState
        state, sources = await self._source_state(active)
        as_of = await self._as_of(active)
        if current["events"] == 0:
            state = "no_data" if state == "available" else state
        breakdown: list[dict[str, Any]] = []
        if d.dimensions:
            if d.scope == "personal" or current["contributors"] == 0:
                breakdown = [{"dims": c.dims, "value": c.value} for c in current["cells"]]
            else:
                breakdown = PrivacyGuard.suppress(current["cells"], threshold, _merge(d.measure.kind))
        return StatResult(
            key=stat_key,
            state=state,
            definition_version=active.version,
            as_of=as_of,
            value=current["value"],
            series=current["series"],
            breakdown=breakdown,
            trend=trend(current["value"], before["value"] if before_ok else None),
            source_states=sources,
            period_start=start,
            period_end=end,
        )

    async def community(self, stat_key: str, active: ActiveDefinition, start: date, end: date) -> StatResult:
        """Community value for system consumers (Wrapped): no viewer, the cohort threshold still applies."""
        d = active.definition
        threshold = d.min_cohort_size or self.config().default_min_cohort_size
        current = await self._compute(active, COMMUNITY, start, end, {})
        if 0 < current["contributors"] < threshold:
            return StatResult(
                stat_key, "insufficient_data", active.version, period_start=start, period_end=end
            )
        breakdown: list[dict[str, Any]] = []
        if d.dimensions:
            breakdown = (
                [{"dims": c.dims, "value": c.value} for c in current["cells"]]
                if current["contributors"] == 0
                else PrivacyGuard.suppress(current["cells"], threshold, _merge(d.measure.kind))
            )
        return StatResult(
            stat_key,
            "available" if current["events"] else "no_data",
            active.version,
            as_of=await self._as_of(active),
            value=current["value"],
            series=current["series"],
            breakdown=breakdown,
            period_start=start,
            period_end=end,
        )

    async def _compute(
        self, active: ActiveDefinition, scope_id: UUID, start: date, end: date, filters: Mapping[str, str]
    ) -> dict[str, Any]:
        d = active.definition
        kind = d.measure.kind
        scope_type = "personal" if d.scope == "personal" else "community"
        where = and_(
            Bucket.stat_key == d.key,
            Bucket.def_version.in_(active.lineage),
            Bucket.scope_type == scope_type,
            Bucket.scope_id == scope_id,
            Bucket.bucket_day.between(start, end),
            *[Bucket.dims[name].astext == value for name, value in filters.items()],
        )
        async with self.database.session() as session:
            rows = (await session.execute(select(Bucket).where(where))).scalars().all()
            hashes = {row.dims_hash for row in rows}
            member_rows: Sequence[Any] = []
            if hashes:
                member_rows = (
                    await session.execute(
                        select(Member.bucket_day, Member.dims_hash, Member.member_hash).where(
                            Member.stat_key == d.key,
                            Member.def_version.in_(active.lineage),
                            Member.scope_type == scope_type,
                            Member.scope_id == scope_id,
                            Member.bucket_day.between(start, end),
                            Member.dims_hash.in_(hashes),
                        )
                    )
                ).all()
        per_day: dict[date, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "sum": 0.0})
        per_cell: dict[str, dict[str, Any]] = {}
        totals: dict[str, Any] = {"count": 0.0, "sum": 0.0, "min": None, "max": None}
        for row in rows:
            day = per_day[row.bucket_day]
            day["count"] += row.count
            day["sum"] += float(row.sum)
            for agg, value in (("min", row.min), ("max", row.max)):
                if value is not None:
                    pick = min if agg == "min" else max
                    day[agg] = float(value) if agg not in day else pick(day[agg], float(value))
                    total = totals[agg]
                    totals[agg] = float(value) if total is None else pick(total, float(value))
            totals["count"] += row.count
            totals["sum"] += float(row.sum)
            cell = per_cell.setdefault(
                row.dims_hash, {"dims": dict(row.dims), "count": 0.0, "sum": 0.0, "min": None, "max": None}
            )
            cell["count"] += row.count
            cell["sum"] += float(row.sum)
            for agg, value in (("min", row.min), ("max", row.max)):
                if value is not None:
                    cell[agg] = (
                        float(value)
                        if cell[agg] is None
                        else (min if agg == "min" else max)(cell[agg], float(value))
                    )
        distinct_day: dict[date, set[str]] = defaultdict(set)
        distinct_cell: dict[str, set[str]] = defaultdict(set)
        contributors_cell: dict[str, set[str]] = defaultdict(set)
        distinct_all: set[str] = set()
        contributors_all: set[str] = set()
        for bucket_day, hashed, member in member_rows:
            if member.startswith("d:"):
                distinct_day[bucket_day].add(member)
                distinct_cell[hashed].add(member)
                distinct_all.add(member)
            else:
                contributors_cell[hashed].add(member)
                contributors_all.add(member)

        def measure(agg: Mapping[str, Any], distinct: set[str]) -> float | None:
            if kind == "count":
                return float(agg["count"])
            if kind == "sum":
                return float(agg["sum"])
            if kind == "avg":
                return round(agg["sum"] / agg["count"], 6) if agg["count"] else None
            if kind in ("min", "max"):
                return agg.get(kind)
            return float(len(distinct))

        series = [
            {"day": day.isoformat(), "value": measure(values, distinct_day.get(day, set()))}
            for day, values in sorted(per_day.items())
        ]
        cells = [
            Cell(
                cell["dims"],
                measure(cell, distinct_cell.get(hashed, set())) or 0.0,
                len(contributors_cell.get(hashed, set())),
            )
            for hashed, cell in per_cell.items()
        ]
        value = (
            measure(totals, distinct_all)
            if rows
            else (0.0 if kind in ("count", "sum", "distinct_count") else None)
        )
        return {
            "value": value,
            "series": series,
            "cells": cells,
            "contributors": len(contributors_all),
            "events": int(totals["count"]),
        }

    async def _source_state(self, active: ActiveDefinition) -> tuple[StatState, dict[str, str]]:
        states: dict[str, str] = {}
        reader = self._port(SERVICE_STATE)
        for service_id in active.definition.sources:
            try:
                view = await reader.get(service_id) if reader is not None else None
            except Exception:
                view = None
            if view is None:
                states[service_id] = "unknown"
            elif view.state in ("unavailable", "maintenance"):
                states[service_id] = "unavailable"
            elif view.state == "degraded":
                states[service_id] = "degraded"
            else:
                states[service_id] = "ok"
        if states and all(s == "unavailable" for s in states.values()):
            return "unavailable", states
        if any(s in ("unavailable", "degraded", "unknown") for s in states.values()):
            return "partial", states
        if await self._lagging(active):
            return "stale", states
        return "available", states

    async def _lag(self, active: ActiveDefinition) -> int:
        stats = self._port(STATS_CAPABILITY)
        if stats is None:
            return 0
        try:
            snapshot = await stats.snapshot()
        except Exception:
            return 0
        return int(snapshot.lag_by_consumer.get(consumer_name(active.definition.key, active.version), 0))

    async def _lagging(self, active: ActiveDefinition) -> bool:
        if await self._lag(active) == 0:
            return False
        stale_after = active.definition.stale_after_s or self.config().stale_after_seconds
        updated = await self._updated(active)
        return updated is None or utc_now(self.clock) - updated > timedelta(seconds=stale_after)

    async def _updated(self, active: ActiveDefinition) -> datetime | None:
        async with self.database.session() as session:
            updated: datetime | None = await session.scalar(
                select(func.max(ProjectionState.updated_at)).where(
                    ProjectionState.stat_key == active.definition.key,
                    ProjectionState.def_version.in_(active.lineage),
                )
            )
            return updated

    async def _as_of(self, active: ActiveDefinition) -> datetime:
        if await self._lag(active) == 0:
            return utc_now(self.clock)
        return await self._updated(active) or utc_now(self.clock)
