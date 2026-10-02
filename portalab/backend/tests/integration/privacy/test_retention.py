"""021 T026 — retention: delete/drop_partition per target with the configured windows; integrity targets
are never touched; every run is recorded; failures are isolated per target."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from portalab.capabilities.retention import RetentionRegistry, RetentionTarget
from portalab.core.time import FixedClock
from portalab.modules.privacy.models import RetentionRun
from portalab.modules.privacy.retention.engine import RetentionEngine
from tests.privacy_fixtures import FullPlatform


async def test_targets_are_applied_and_recorded(full: FullPlatform, clock: FixedClock) -> None:
    now = clock.now()
    async with full.database.engine.begin() as conn:
        for age in (40, 1):
            await conn.execute(
                text("INSERT INTO core.live_event (topic, payload, created_at) VALUES ('t', '{}', :at)"),
                {"at": now - timedelta(days=age)},
            )
    registry = RetentionRegistry()
    registry.register(
        RetentionTarget("core.live_event", "core.live_event", "technical", "created_at", "delete", "t")
    )
    registry.register(
        RetentionTarget(
            "ledger", "identity.account_state_history", "history", "occurred_at", "drop_partition", "t", True
        )
    )
    registry.register(RetentionTarget("broken", "nope.missing", "technical", "created_at", "delete", "t"))
    engine = RetentionEngine(
        full.database, full.authz.events, registry=registry, config=full.privacy.config, clock=clock
    )
    outcomes = {outcome.target: outcome for outcome in await engine.run()}
    assert outcomes["core.live_event"].status == "applied" and outcomes["core.live_event"].rows == 1
    assert outcomes["broken"].status == "failed"  # isolated: the others still ran
    async with full.database.engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM core.live_event"))).scalar() == 1
    async with full.database.session() as session:
        runs = {run.target: run.status for run in (await session.execute(select(RetentionRun))).scalars()}
    assert runs["core.live_event"] == "applied" and runs["broken"] == "failed"


async def test_no_window_means_no_cleanup(full: FullPlatform, clock: FixedClock) -> None:
    config = replace(
        full.privacy.config, retention_days={**full.privacy.config.retention_days, "technical": None}
    )
    registry = RetentionRegistry()
    registry.register(
        RetentionTarget("core.live_event", "core.live_event", "technical", "created_at", "delete", "t")
    )
    engine = RetentionEngine(full.database, full.authz.events, registry=registry, config=config, clock=clock)
    assert (await engine.run())[0].status == "skipped"


async def test_audit_partitions_follow_the_audit_window(full: FullPlatform) -> None:
    now = datetime.now(UTC)
    async with full.database.engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE audit.audit_entries_p201901 PARTITION OF audit.audit_entries "
                "FOR VALUES FROM ('2019-01-01') TO ('2019-02-01')"
            )
        )
    registry = RetentionRegistry()
    registry.register(
        RetentionTarget("audit", "audit.audit_entries", "audit", "occurred_at", "drop_partition", "t")
    )
    engine = RetentionEngine(
        full.database, full.authz.events, registry=registry, config=full.privacy.config, clock=FixedClock(now)
    )
    assert (await engine.run())[0].rows == 1
