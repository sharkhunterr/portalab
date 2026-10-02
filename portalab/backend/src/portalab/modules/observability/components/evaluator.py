"""Two-axis health evaluator (T012; R1, FR-003..005).

For every observed component the technical checks (up, latency, error rate) and the functional checks
(doing its job: lag, freshness, success window) are evaluated **separately**. An axis takes the worst of
its checks; a check that raises or times out is ``unknown`` — never green; an axis without checks is
``unknown`` (marked ``unobserved`` in the reason so it is not reported as a problem). The reported status is
``healthy`` only when both axes are ``ok``; "technically up, functionally failing" is ``degraded``.
Transitions are historized per axis and announced once (``observability.health_changed``).
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select

from portalab.capabilities.observability import Check, CheckResult, ObservableRegistry, ObservedComponent
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.models import ComponentHealth, HealthHistory
from portalab.modules.observability.observability import metric_part, metrics

Axis = Literal["technical", "functional"]
_RANK = {"ok": 0, "degraded": 1, "unknown": 2, "down": 3, "failing": 3}
CHECK_TIMEOUT_SECONDS = 5.0


def _axis_state(axis: Axis, state: str) -> str:
    if axis == "technical":
        return "down" if state == "failing" else state
    return "failing" if state == "down" else state


def worst(axis: Axis, results: Sequence[CheckResult]) -> str:
    if not results:
        return "unknown"
    states = [_axis_state(axis, r.state) for r in results]
    return max(states, key=lambda s: _RANK.get(s, 2))


def reported_status(technical: str, functional: str) -> str:
    if technical == "ok" and functional == "ok":
        return "healthy"
    if technical == "down":
        return "down"
    if technical == "unknown" and functional == "unknown":
        return "unknown"
    return "degraded"


@dataclass(frozen=True, slots=True)
class Evaluation:
    component: str
    technical: str
    functional: str
    reason: dict[str, Any]

    @property
    def status(self) -> str:
        return reported_status(self.technical, self.functional)


async def run_check(check: Check, limit_seconds: float = CHECK_TIMEOUT_SECONDS) -> CheckResult:
    try:
        result = await asyncio.wait_for(check.evaluate(), timeout=limit_seconds)
    except TimeoutError:
        return CheckResult("unknown", f"{check.name} did not answer in time")
    except Exception as exc:
        metrics.increment("observability.check_failures")
        return CheckResult("unknown", f"{check.name} failed ({type(exc).__name__})")
    return (
        result
        if isinstance(result, CheckResult)
        else CheckResult("unknown", f"{check.name} returned nothing")
    )


async def evaluate_component(component: ObservedComponent) -> Evaluation:
    technical = [await run_check(c) for c in component.technical_checks]
    functional = [await run_check(c) for c in component.functional_checks]

    def describe(checks: Sequence[Check], results: Sequence[CheckResult]) -> list[dict[str, Any]]:
        return [
            {"check": c.name, "state": r.state, "reason": r.reason, "facts": dict(r.facts)}
            for c, r in zip(checks, results, strict=True)
        ]

    return Evaluation(
        component.name,
        worst("technical", technical),
        worst("functional", functional),
        {
            "technical": describe(component.technical_checks, technical),
            "functional": describe(component.functional_checks, functional),
            "unobserved": [
                axis
                for axis, checks in (
                    ("technical", component.technical_checks),
                    ("functional", component.functional_checks),
                )
                if not checks
            ],
        },
    )


class HealthEvaluator:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        registry: ObservableRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.registry = registry
        self.clock = clock

    async def evaluate_all(self) -> list[Evaluation]:
        evaluations = []
        for component in await self.registry.components():
            evaluation = await evaluate_component(component)
            await self.store(component, evaluation)
            evaluations.append(evaluation)
        return evaluations

    async def store(self, component: ObservedComponent, evaluation: Evaluation) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(ComponentHealth, component.name, with_for_update=True)
            changes: list[tuple[Axis, str | None, str]] = []
            if row is None:
                row = ComponentHealth(
                    component=component.name,
                    owner=component.owner,
                    technical=evaluation.technical,
                    functional=evaluation.functional,
                    since=now,
                    seq=0,
                    reason=evaluation.reason,
                    evaluated_at=now,
                )
                uow.session.add(row)
                changes = [
                    ("technical", None, evaluation.technical),
                    ("functional", None, evaluation.functional),
                ]
            else:
                if row.technical != evaluation.technical:
                    changes.append(("technical", row.technical, evaluation.technical))
                if row.functional != evaluation.functional:
                    changes.append(("functional", row.functional, evaluation.functional))
                row.technical, row.functional = evaluation.technical, evaluation.functional
                row.reason, row.evaluated_at, row.owner = evaluation.reason, now, component.owner
                if changes:
                    row.since = now
            for axis, before, after in changes:
                row.seq += 1
                summary = _summary(evaluation.reason.get(axis, []))
                uow.session.add(
                    HealthHistory(
                        component=component.name,
                        axis=axis,
                        from_state=before,
                        to_state=after,
                        occurred_at=now,
                        reason=summary,
                    )
                )
                await self.events.publish(
                    uow.session,
                    "observability.health_changed",
                    {
                        "component": component.name,
                        "axis": axis,
                        "from_state": before,
                        "to_state": after,
                        "seq": row.seq,
                        "status": evaluation.status,
                    },
                    occurred_at=now,
                    subject=SubjectRef("component", component.name),
                    source="observability",
                )
                metrics.increment(f"observability.health_changes.{metric_part(axis)}")

    async def current(self, component: str) -> ComponentHealth | None:
        async with self.database.session() as session:
            return await session.get(ComponentHealth, component)

    async def all(self) -> list[ComponentHealth]:
        async with self.database.session() as session:
            return list(
                (await session.execute(select(ComponentHealth).order_by(ComponentHealth.component))).scalars()
            )


def _summary(items: list[dict[str, Any]]) -> str:
    bad = [f"{i['check']}: {i['reason']}" for i in items if i["state"] != "ok" and i.get("reason")]
    return "; ".join(bad)[:256]


def health_out(row: ComponentHealth, *, at: datetime | None = None) -> dict[str, Any]:
    return {
        "component": row.component,
        "owner": row.owner,
        "technical": row.technical,
        "functional": row.functional,
        "status": reported_status(row.technical, row.functional),
        "since": row.since.isoformat(),
        "evaluated_at": row.evaluated_at.isoformat(),
        "reason": row.reason,
    }
