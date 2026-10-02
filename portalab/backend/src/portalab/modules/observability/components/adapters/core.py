"""Core component adapters (T017): events (007), jobs and database (kernel), the portal as a whole,
automations (019 port), AI (018, metadata-only metrics) and Observability itself (R8 self-component).

Adapters read facts through capabilities or kernel tables and turn them into check results using the
configured thresholds (``observability.thresholds.*``) — nothing is hard-coded (FR-014)."""

import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, text

from portalab.capabilities.events import STATS_CAPABILITY
from portalab.capabilities.observability import (
    AUTOMATION_STATUS,
    Check,
    CheckResult,
    DiagnosticAction,
    ObservableRegistry,
    ObservedComponent,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.jobs.models import Job
from portalab.core.metrics import MetricsRegistry
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.models import ComponentHealth, MetricSample
from portalab.modules.observability.settings import ObservabilityConfig

OWNER = "module:observability"
ConfigGetter = Callable[[], ObservabilityConfig]


def _provider(capabilities: CapabilityRegistry, name: str) -> Any:
    try:
        providers = capabilities.system_providers(name)
    except Exception:
        return None
    return providers[0].provider if providers else None


def events_component(capabilities: CapabilityRegistry, config: ConfigGetter) -> ObservedComponent:
    async def pipeline() -> CheckResult:
        stats = _provider(capabilities, STATS_CAPABILITY)
        if stats is None:
            return CheckResult("unknown", "event statistics are not available")
        snap = await stats.snapshot()
        return CheckResult("ok", "event store reachable", {"head_seq": snap.head_seq})

    async def delivery() -> CheckResult:
        stats = _provider(capabilities, STATS_CAPABILITY)
        if stats is None:
            return CheckResult("unknown", "event statistics are not available")
        snap = await stats.snapshot()
        cfg = config()
        lag = max(snap.lag_by_consumer.values(), default=0)
        facts = {"max_lag": lag, "dead_letters": snap.dead_letters, "quarantined": snap.quarantined}
        if lag >= cfg.events_lag_failing:
            return CheckResult("failing", f"a consumer is {lag} events behind", facts)
        if snap.dead_letters or lag >= cfg.events_lag_degraded or snap.quarantined:
            return CheckResult("degraded", "dead letters, quarantine or consumer lag", facts)
        return CheckResult("ok", "consumers keep up", facts)

    return ObservedComponent(
        "events",
        OWNER,
        label="Events & history",
        technical_checks=(Check("event_store", pipeline),),
        functional_checks=(Check("consumers", delivery),),
        diagnostics=(
            DiagnosticAction(
                "view_dead_letters",
                "View dead letters",
                "GET",
                "/api/v1/admin/events/deliveries?status=dead",
                "events.manage",
            ),
            DiagnosticAction(
                "view_quarantine",
                "View quarantine",
                "GET",
                "/api/v1/admin/events/quarantine",
                "events.manage",
            ),
        ),
        impact=3,
        criticality=2,
    )


def jobs_component(database: Database, config: ConfigGetter, clock: Clock | None) -> ObservedComponent:
    async def queue() -> CheckResult:
        now = utc_now(clock)
        cfg = config()
        async with database.session() as session:
            dead = int(
                await session.scalar(select(func.count()).select_from(Job).where(Job.status == "dead")) or 0
            )
            failed = int(
                await session.scalar(select(func.count()).select_from(Job).where(Job.status == "failed")) or 0
            )
            oldest = await session.scalar(
                select(func.min(Job.run_at)).where(Job.status == "queued", Job.run_at <= now)
            )
        waiting = (now - oldest).total_seconds() / 60 if oldest else 0.0
        facts = {"dead": dead, "failed": failed, "oldest_due_minutes": round(waiting, 1)}
        if waiting >= cfg.jobs_queued_age_minutes:
            return CheckResult("failing", "due jobs are not being picked up (is the worker running?)", facts)
        if dead + failed >= cfg.jobs_failed_degraded:
            return CheckResult("degraded", "some jobs failed", facts)
        return CheckResult("ok", "the queue is draining", facts)

    return ObservedComponent(
        "jobs",
        OWNER,
        label="Background jobs",
        functional_checks=(Check("queue", queue),),
        impact=3,
        criticality=2,
    )


def database_component(database: Database, config: ConfigGetter) -> ObservedComponent:
    async def ping() -> CheckResult:
        started = time.monotonic()
        async with database.session() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.monotonic() - started) * 1000
        facts = {"latency_ms": round(latency, 1)}
        if latency > config().db_latency_degraded_ms:
            return CheckResult("degraded", "the database answers slowly", facts)
        return CheckResult("ok", "the database answers", facts)

    return ObservedComponent(
        "db", OWNER, label="Database", technical_checks=(Check("ping", ping),), impact=5, criticality=5
    )


def portal_component(database: Database) -> ObservedComponent:
    """The whole portal: functionally degraded as soon as any other component is."""

    async def components() -> CheckResult:
        async with database.session() as session:
            rows = (
                await session.execute(
                    select(
                        ComponentHealth.component, ComponentHealth.technical, ComponentHealth.functional
                    ).where(ComponentHealth.component != "portal")
                )
            ).all()
        bad = sorted(c for c, t, f in rows if t in ("down", "degraded") or f in ("failing", "degraded"))
        if not rows:
            return CheckResult("unknown", "nothing evaluated yet")
        if bad:
            return CheckResult(
                "degraded", f"{len(bad)} component(s) need attention", {"components": bad[:20]}
            )
        return CheckResult("ok", "every component is healthy")

    return ObservedComponent(
        "portal",
        OWNER,
        label="Portal",
        functional_checks=(Check("components", components),),
        impact=5,
        criticality=3,
    )


def automations_component(capabilities: CapabilityRegistry) -> ObservedComponent:
    async def engine() -> CheckResult:
        port = _provider(capabilities, AUTOMATION_STATUS)
        if port is None:
            return CheckResult("unknown", "the automation engine is not installed")
        status = await port.status()
        facts = {
            "active_rules": status.active_rules,
            "executions": status.executions,
            "failures": status.failures,
            "suspended": [dict(s) for s in status.suspended][:20],
        }
        if status.suspended:
            reasons = ", ".join(f"{s.get('rule_id')}: {s.get('reason')}" for s in status.suspended[:3])
            return CheckResult("degraded", f"suspended rules — {reasons}", facts)
        if status.executions and status.failures / status.executions > 0.5:
            return CheckResult("failing", "most executions fail", facts)
        return CheckResult("ok", "rules run", facts)

    return ObservedComponent(
        "automations", OWNER, label="Automations", functional_checks=(Check("engine", engine),), impact=2
    )


def ai_component(database: Database, config: ConfigGetter, clock: Clock | None) -> ObservedComponent:
    """AI is observed from metadata-only metrics (``report_ai_call``): never from conversation content."""

    async def failure_rate() -> CheckResult:
        since = utc_now(clock) - timedelta(hours=1)
        async with database.session() as session:
            rows = (
                await session.execute(
                    select(MetricSample.labels, MetricSample.count).where(
                        MetricSample.component == "ai",
                        MetricSample.metric == "ai.requests",
                        MetricSample.sampled_at >= since,
                    )
                )
            ).all()
        total = sum(count for _, count in rows)
        if not total:
            return CheckResult("unknown", "no AI request in the last hour")
        failed = sum(count for labels, count in rows if labels.get("outcome") in ("error", "timeout"))
        rate = failed / total
        facts = {"requests": total, "failed": failed, "failure_rate": round(rate, 3)}
        if rate > config().ai_failure_rate_degraded:
            return CheckResult("degraded", "many AI requests fail or time out", facts)
        return CheckResult("ok", "AI requests succeed", facts)

    return ObservedComponent(
        "ai", OWNER, label="AI assistant", functional_checks=(Check("failure_rate", failure_rate),)
    )


def self_component(
    metrics_registry: MetricsRegistry, collector: Any, clock: Clock | None
) -> ObservedComponent:
    async def pipeline() -> CheckResult:
        stats = metrics_registry.stats()
        last = collector.stats.last_flush_at
        lag = (utc_now(clock) - last).total_seconds() if last else None
        facts = {**stats, "collector_failures": collector.stats.failures, "collector_lag_seconds": lag}
        if collector.stats.failures and collector.stats.dropped_batches:
            return CheckResult("degraded", "observability data was dropped", facts)
        if stats["dropped"]:
            return CheckResult("degraded", "the hook queue overflowed", facts)
        return CheckResult("ok", "observability keeps up", facts)

    return ObservedComponent(
        "observability", OWNER, label="Observability", functional_checks=(Check("pipeline", pipeline),)
    )


def register_core(
    registry: ObservableRegistry,
    *,
    database: Database,
    capabilities: CapabilityRegistry,
    config: ConfigGetter,
    metrics_registry: MetricsRegistry,
    collector: Any,
    clock: Clock | None,
) -> None:
    for component in (
        events_component(capabilities, config),
        jobs_component(database, config, clock),
        database_component(database, config),
        portal_component(database),
        automations_component(capabilities),
        ai_component(database, config, clock),
        self_component(metrics_registry, collector, clock),
    ):
        registry.declare(component)
