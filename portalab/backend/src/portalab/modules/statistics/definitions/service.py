"""``DefinitionService`` (T007; R1, R4, R11): admin-defined statistics as **closed-set** documents.

* validation: every event type must be registered (007) and every field used (filter, dimensions, measure)
  must be an envelope field (``actor``, ``subject``, ``source``) or marked ``aggregatable`` by **all** the
  event types; a community/global privacy threshold never goes below ``statistics.defaultMinCohortSize``;
* versions are append-only; one version is active per key; activation records the *lineage*:
  ``forward_only`` keeps history under the earlier versions (the new version only folds events after its
  activation), ``rebuild`` recomputes everything from the event history under the new version;
* every change is audited (activation and rebuild are sensitive) and announced as
  ``statistics.definition_changed`` (consumers refresh their projections).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.events import EventTypeRegistry
from portalab.capabilities.statistics import ENVELOPE_FIELDS, StatisticDefinition
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.statistics.models import Definition, DefinitionStatus, ProjectionState
from portalab.modules.statistics.settings import StatisticsConfig

ChangePolicy = Literal["forward_only", "rebuild"]


class InvalidDefinition(ValidationFailed):
    default_code = "statistics.invalid_definition"
    default_title = "Invalid statistic definition"


class UnknownStatistic(NotFound):
    default_code = "statistics.unknown"
    default_title = "Unknown statistic"


@dataclass(frozen=True, slots=True)
class ActiveDefinition:
    definition: StatisticDefinition
    version: int
    lineage: tuple[int, ...]  # versions whose buckets make up the history (oldest first)


def numeric_measure(definition: StatisticDefinition) -> bool:
    return definition.measure.kind in ("sum", "avg", "min", "max")


class DefinitionService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        event_types: EventTypeRegistry,
        config: Callable[[], StatisticsConfig],
        *,
        head_seq: Callable[[], Any] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.event_types = event_types
        self.config = config
        self.head_seq = head_seq
        self.clock = clock

    # --- validation ----------------------------------------------------------------------------------
    def parse(self, raw: Mapping[str, Any] | StatisticDefinition) -> StatisticDefinition:
        if isinstance(raw, StatisticDefinition):
            definition = raw
        else:
            try:
                definition = StatisticDefinition.model_validate(dict(raw))
            except ValidationError as exc:
                raise InvalidDefinition(
                    "This statistic definition is not valid.",
                    extensions={"errors": [e["msg"] for e in exc.errors()][:10]},
                ) from exc
        self.validate(definition)
        return definition

    def validate(self, definition: StatisticDefinition) -> None:
        errors: list[str] = []
        allowed: set[str] | None = None
        for name in definition.event_types:
            registered = self.event_types.get(name)
            if registered is None:
                errors.append(f"unknown event type {name!r}")
                continue
            fields = set(registered.aggregatable)
            allowed = fields if allowed is None else allowed & fields
        usable = ENVELOPE_FIELDS | (allowed or set())
        for field in sorted(definition.fields()):
            if field not in usable:
                errors.append(f"field {field!r} is not aggregatable for every event type")
        measure = definition.measure
        if numeric_measure(definition) and (measure.field is None or measure.field in ENVELOPE_FIELDS):
            errors.append(f"measure {measure.kind} needs a numeric event field")
        if measure.kind == "count" and measure.field is not None:
            errors.append("a count measure takes no field")
        floor = max(1, self.config().default_min_cohort_size)
        if (
            definition.scope != "personal"
            and definition.min_cohort_size is not None
            and definition.min_cohort_size < floor
        ):
            errors.append(f"min_cohort_size must be at least {floor}")
        if definition.scope == "personal" and definition.dimensions and "actor" in definition.dimensions:
            errors.append("a personal statistic cannot be split by actor")
        if errors:
            raise InvalidDefinition(
                "This statistic definition is not valid.", extensions={"errors": errors[:10]}
            )

    # --- versions ------------------------------------------------------------------------------------
    async def save(
        self,
        actor: Principal | None,
        raw: Mapping[str, Any] | StatisticDefinition,
        *,
        change_policy: ChangePolicy = "forward_only",
        source: str = "admin",
        force: bool = False,
    ) -> int:
        """Store a new version (draft unless nothing is active yet and ``source`` is builtin)."""
        definition = self.parse(raw)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            latest = int(
                await session.scalar(
                    select(func.coalesce(func.max(Definition.version), 0)).where(
                        Definition.key == definition.key
                    )
                )
                or 0
            )
            if latest:
                current = await session.get(Definition, (definition.key, latest))
                if (
                    not force
                    and current is not None
                    and current.definition == definition.model_dump(mode="json")
                ):
                    return latest  # unchanged: no new version
            version = latest + 1
            session.add(
                Definition(
                    key=definition.key,
                    version=version,
                    domain=definition.domain,
                    definition=definition.model_dump(mode="json"),
                    change_policy=change_policy,
                    source=source[:80],
                    created_by=(actor.acting_for or actor.user_id) if actor else None,
                    created_at=now,
                )
            )
            status = await session.get(DefinitionStatus, definition.key, with_for_update=True)
            if status is None:
                session.add(
                    DefinitionStatus(
                        key=definition.key,
                        status="draft",
                        active_version=None,
                        latest_version=version,
                        updated_at=now,
                    )
                )
            else:
                status.latest_version, status.updated_at = version, now
            await session.flush()
            if actor is not None:
                await self._audit(
                    session, actor, "statistics.definition_saved", definition.key, {"version": version}, False
                )
            await self._announce(session, definition.key, version, "saved", actor)
            return version

    async def activate(self, actor: Principal | None, key: str, version: int | None = None) -> int:
        now = utc_now(self.clock)
        head = int(await self.head_seq()) if self.head_seq is not None else 0
        async with self.database.unit_of_work() as uow:
            session = uow.session
            status = await session.get(DefinitionStatus, key, with_for_update=True)
            if status is None:
                raise UnknownStatistic("This statistic does not exist.")
            version = version or status.latest_version
            row = await session.get(Definition, (key, version))
            if row is None:
                raise UnknownStatistic("This statistic version does not exist.")
            previous = status.active_version
            if previous == version and status.status == "active":
                return version
            rebuild = row.change_policy == "rebuild" or previous is None
            if not rebuild and previous is not None:
                # forward_only: the new version folds events after now; the previous one stops here
                await self._bounds(session, key, previous, stop_after=head, now=now)
                await self._bounds(session, key, version, start_after=head, now=now)
            else:
                await self._bounds(session, key, version, now=now)
            status.status, status.active_version, status.updated_at = "active", version, now
            await self._set_lineage(session, key, version, rebuild)
            if actor is not None:
                await self._audit(
                    session,
                    actor,
                    "statistics.definition_activated",
                    key,
                    {"version": version, "rebuild": rebuild},
                    True,
                )
            await self._announce(session, key, version, "activated", actor)
            return version

    async def retire(self, actor: Principal, key: str) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            status = await uow.session.get(DefinitionStatus, key, with_for_update=True)
            if status is None:
                raise UnknownStatistic("This statistic does not exist.")
            status.status, status.active_version, status.updated_at = "retired", None, now
            await self._audit(uow.session, actor, "statistics.definition_retired", key, {}, True)
            await self._announce(uow.session, key, status.latest_version, "retired", actor)

    async def _bounds(
        self,
        session: AsyncSession,
        key: str,
        version: int,
        *,
        start_after: int | None = None,
        stop_after: int | None = None,
        now: Any,
    ) -> None:
        values: dict[str, Any] = {"stat_key": key, "def_version": version, "events": 0, "updated_at": now}
        update: dict[str, Any] = {"updated_at": now}
        if start_after is not None:
            values["start_after_seq"] = update["start_after_seq"] = start_after
        if stop_after is not None:
            values["stop_after_seq"] = update["stop_after_seq"] = stop_after
        await session.execute(
            insert(ProjectionState)
            .values(**values)
            .on_conflict_do_update(index_elements=["stat_key", "def_version"], set_=update)
        )

    async def _set_lineage(self, session: AsyncSession, key: str, version: int, rebuild: bool) -> None:
        state = await session.get(ProjectionState, (key, version))
        if state is None:
            return
        if rebuild:
            state.lineage_from = version
        else:
            older = [
                s
                for s in (
                    await session.execute(
                        select(ProjectionState).where(
                            ProjectionState.stat_key == key, ProjectionState.def_version < version
                        )
                    )
                ).scalars()
            ]
            previous = max(older, key=lambda s: s.def_version, default=None)
            state.lineage_from = (
                previous.lineage_from if previous is not None and previous.lineage_from else version
            )

    # --- reading -------------------------------------------------------------------------------------
    async def active(self) -> list[ActiveDefinition]:
        async with self.database.session() as session:
            statuses = (
                (await session.execute(select(DefinitionStatus).where(DefinitionStatus.status == "active")))
                .scalars()
                .all()
            )
            out = []
            for status in statuses:
                if status.active_version is None:
                    continue
                out.append(await self._active(session, status.key, status.active_version))
            return out

    async def get_active(self, key: str) -> ActiveDefinition | None:
        async with self.database.session() as session:
            status = await session.get(DefinitionStatus, key)
            if status is None or status.status != "active" or status.active_version is None:
                return None
            return await self._active(session, key, status.active_version)

    async def _active(self, session: AsyncSession, key: str, version: int) -> ActiveDefinition:
        row = await session.get(Definition, (key, version))
        assert row is not None
        state = await session.get(ProjectionState, (key, version))
        start = state.lineage_from if state is not None and state.lineage_from else version
        lineage = tuple(range(start, version + 1))
        return ActiveDefinition(StatisticDefinition.model_validate(row.definition), version, lineage)

    async def versions_in_projection(self) -> list[tuple[StatisticDefinition, int, int | None, int | None]]:
        """``(definition, version, start_after, stop_after)`` of every version whose consumer must run:
        the active versions and the earlier versions of their lineage (still finishing their range)."""
        out = []
        async with self.database.session() as session:
            for active in await self.active():
                for version in active.lineage:
                    row = await session.get(Definition, (active.definition.key, version))
                    state = await session.get(ProjectionState, (active.definition.key, version))
                    if row is None:
                        continue
                    out.append(
                        (
                            StatisticDefinition.model_validate(row.definition),
                            version,
                            state.start_after_seq if state else None,
                            state.stop_after_seq if state else None,
                        )
                    )
        return out

    async def listing(self) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            statuses = (
                (await session.execute(select(DefinitionStatus).order_by(DefinitionStatus.key)))
                .scalars()
                .all()
            )
            out = []
            for status in statuses:
                latest = await session.get(Definition, (status.key, status.latest_version))
                out.append(
                    {
                        "key": status.key,
                        "status": status.status,
                        "active_version": status.active_version,
                        "latest_version": status.latest_version,
                        "domain": latest.domain if latest else None,
                        "source": latest.source if latest else None,
                        "definition": latest.definition if latest else None,
                        "change_policy": latest.change_policy if latest else None,
                    }
                )
            return out

    async def versions(self, key: str) -> Sequence[Definition]:
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(Definition).where(Definition.key == key).order_by(Definition.version)
                    )
                )
                .scalars()
                .all()
            )
            if not rows:
                raise UnknownStatistic("This statistic does not exist.")
            return list(rows)

    # --- internals -----------------------------------------------------------------------------------
    async def _audit(
        self,
        session: AsyncSession,
        actor: Principal,
        action: str,
        key: str,
        context: Mapping[str, Any],
        sensitive: bool,
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("statistic", key),
                decision="allow",
                result="success",
                context=dict(context),
                sensitive=sensitive,
            ),
        )

    async def _announce(
        self, session: AsyncSession, key: str, version: int, change: str, actor: Principal | None
    ) -> None:
        await self.events.publish(
            session,
            "statistics.definition_changed",
            {"statistic": key, "version": version, "change": change},
            occurred_at=utc_now(self.clock),
            actor=actor,
            source="statistics",
            dedup_key=f"statistics.definition:{key}:{version}:{change}:{utc_now(self.clock).isoformat()}",
        )
