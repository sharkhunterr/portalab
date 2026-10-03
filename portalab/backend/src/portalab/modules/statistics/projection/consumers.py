"""Projection (T011; R2): one 007 consumer per statistic version folds its events into daily buckets
(``stats.buckets``) and distinct members (``stats.members``).

* idempotent and replay-safe: the event id is recorded in ``stats.applied_events`` **in the same
  transaction** as the bucket update, so a redelivered or replayed event never counts twice;
* deterministic: the bucket day is the event's ``occurred_at`` in the statistics time zone (late or
  out-of-order events land in their own day);
* a new consumer starts at the beginning of the event log, so activating a statistic computes its
  history; ``forward_only`` versions are bounded by ``start_after_seq`` / ``stop_after_seq``;
* community buckets also record their contributors (salted hashes) for privacy thresholds.
"""

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.events import Consumer, ConsumerContext, ConsumerRegistry, Envelope
from portalab.capabilities.statistics import StatisticDefinition
from portalab.core.db import Database
from portalab.modules.statistics.models import COMMUNITY, AppliedEvent, Bucket, Member, ProjectionState
from portalab.modules.statistics.observability import metric_part, metrics
from portalab.modules.statistics.period.resolver import local_day, zone

OWNER = "module:statistics"
PREFIX = "statistics.projection."


def consumer_name(key: str, version: int) -> str:
    return f"{PREFIX}{key}.v{version}"


def field_value(envelope: Envelope, name: str) -> Any:
    match name:
        case "actor":
            return str(envelope.actor_user_id) if envelope.actor_user_id else None
        case "subject":
            return envelope.subject_id
        case "source":
            return envelope.source_system
    return envelope.payload.get(name)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def matches(definition: StatisticDefinition, envelope: Envelope) -> bool:
    for clause in definition.filter:
        value = field_value(envelope, clause.field)
        wanted = clause.value
        match clause.op:
            case "eq":
                ok = value == wanted or str(value) == str(wanted)
            case "ne":
                ok = not (value == wanted or str(value) == str(wanted))
            case "in":
                ok = str(value) in {str(v) for v in (wanted if isinstance(wanted, list) else [wanted])}
            case _:
                left, right = _number(value), _number(wanted)
                if left is None or right is None:
                    return False
                ok = {
                    "gt": left > right,
                    "gte": left >= right,
                    "lt": left < right,
                    "lte": left <= right,
                }[clause.op]
        if not ok:
            return False
    return True


def dims_of(definition: StatisticDefinition, envelope: Envelope) -> dict[str, str]:
    return {name: str(field_value(envelope, name) or "") for name in definition.dimensions}


def dims_hash(dims: Mapping[str, str]) -> str:
    return hashlib.sha1(json.dumps(dims, sort_keys=True).encode(), usedforsecurity=False).hexdigest()


class Projection:
    def __init__(
        self,
        database: Database,
        salt: bytes,
        timezone: Callable[[], str],
    ) -> None:
        self.database = database
        self.salt = salt
        self.timezone = timezone

    def member(self, namespace: str, value: str) -> str:
        """``c:`` contributors / ``d:`` distinct values — salted, never reversible to a user id."""
        digest = hmac.new(self.salt, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()
        return f"{namespace}:{digest[:62]}"

    def consumer(
        self, definition: StatisticDefinition, version: int, start_after: int | None, stop_after: int | None
    ) -> Consumer:
        async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
            if start_after is not None and envelope.seq <= start_after:
                return
            if stop_after is not None and envelope.seq > stop_after:
                return
            await self.apply(definition, version, envelope)

        return Consumer(
            consumer_name(definition.key, version),
            frozenset(definition.event_types),
            handle,
            OWNER,
            replay_safe=True,
        )

    async def apply(self, definition: StatisticDefinition, version: int, envelope: Envelope) -> bool:
        """Fold one event; ``False`` when it does not match or was already applied."""
        if not matches(definition, envelope):
            return False
        personal = definition.scope == "personal"
        actor = envelope.actor_user_id
        if personal and actor is None:
            return False
        scope_type = "personal" if personal else "community"
        scope_id: UUID = actor if personal and actor is not None else COMMUNITY
        day = local_day(envelope.occurred_at, zone(self.timezone()))
        dims = dims_of(definition, envelope)
        hashed = dims_hash(dims)
        measure = definition.measure
        value = (
            1.0
            if measure.kind in ("count", "distinct_count")
            else _number(field_value(envelope, measure.field or ""))
        )
        if value is None:
            return False
        key = definition.key
        async with self.database.unit_of_work() as uow:
            session = uow.session
            applied = (
                await session.execute(
                    insert(AppliedEvent)
                    .values(stat_key=key, def_version=version, event_id=envelope.event_id, bucket_day=day)
                    .on_conflict_do_nothing()
                    .returning(AppliedEvent.event_id)
                )
            ).scalar_one_or_none()
            if applied is None:
                return False  # already folded (redelivery or replay)
            base = {
                "stat_key": key,
                "def_version": version,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "bucket_day": day,
                "dims_hash": hashed,
            }
            await session.execute(
                insert(Bucket)
                .values(**base, dims=dims, count=1, sum=value, min=value, max=value)
                .on_conflict_do_update(
                    constraint="pk_buckets",
                    set_={
                        "count": Bucket.count + 1,
                        "sum": Bucket.sum + value,
                        "min": func.least(Bucket.min, value),
                        "max": func.greatest(Bucket.max, value),
                    },
                )
            )
            members = []
            if not personal and actor is not None:
                members.append(self.member("c", str(actor)))  # contributors (privacy threshold)
            if measure.kind == "distinct_count":
                distinct = field_value(envelope, measure.field or "actor")
                if distinct is not None:
                    members.append(self.member("d", str(distinct)))
            for member in members:
                await session.execute(
                    insert(Member).values(**base, member_hash=member).on_conflict_do_nothing()
                )
            await session.execute(
                insert(ProjectionState)
                .values(
                    stat_key=key,
                    def_version=version,
                    last_event_at=envelope.occurred_at,
                    events=1,
                    updated_at=_now(envelope),
                )
                .on_conflict_do_update(
                    index_elements=["stat_key", "def_version"],
                    set_={
                        "events": ProjectionState.events + 1,
                        "last_event_at": func.greatest(ProjectionState.last_event_at, envelope.occurred_at),
                        "updated_at": _now(envelope),
                    },
                )
            )
        metrics.increment(f"statistics.projection.{metric_part(key)}.events")
        return True


def _now(envelope: Envelope) -> datetime:
    return envelope.received_at


def sync_consumers(
    registry: ConsumerRegistry,
    projection: Projection,
    versions: list[tuple[StatisticDefinition, int, int | None, int | None]],
) -> int:
    """Make the registry hold exactly one consumer per projected version (others are removed)."""
    wanted = {consumer_name(d.key, v): (d, v, start, stop) for d, v, start, stop in versions}
    for existing in list(registry.all()):
        if existing.name.startswith(PREFIX) and existing.name not in wanted:
            registry.remove(existing.name)
    for definition, version, start, stop in wanted.values():
        registry.replace(projection.consumer(definition, version, start, stop))
    return len(wanted)
