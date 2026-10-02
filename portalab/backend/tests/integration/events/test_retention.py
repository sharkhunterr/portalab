"""007 T023/T024 — partitions dropped per class window; business events outlive technical ones; dedup keys
and finished deliveries pruned."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from portalab.capabilities.retention import RetentionRegistry
from portalab.core.time import FixedClock
from portalab.modules.events.retention import register_targets
from portalab.modules.events.settings import EventsConfig
from portalab.modules.privacy.retention.engine import RetentionEngine
from tests.events_fixtures import EventsHarness


async def test_class_windows(ev: EventsHarness, monkeypatch: object) -> None:
    import portalab.modules.events.retention as module

    registry = RetentionRegistry()
    module.default_retention_targets = registry  # type: ignore[attr-defined]
    try:
        register_targets(
            lambda: EventsConfig(
                business_retention_months=24, technical_retention_days=30, dedup_key_retention_days=30
            )
        )
    finally:
        from portalab.capabilities.retention import default_retention_targets

        module.default_retention_targets = default_retention_targets  # type: ignore[attr-defined]
    async with ev.full.database.engine.begin() as conn:
        for klass in ("business", "technical"):
            await conn.execute(
                text(
                    f"CREATE TABLE events.events_{klass}_p202001 PARTITION OF events.events_{klass} "
                    "FOR VALUES FROM ('2020-01-01') TO ('2020-02-01')"
                )
            )
        now = datetime.now(UTC)
        await conn.execute(
            text("INSERT INTO events.dedup_keys VALUES ('t', 'old', gen_random_uuid(), :at)"),
            {"at": now - timedelta(days=90)},
        )
        await conn.execute(
            text("INSERT INTO events.dedup_keys VALUES ('t', 'new', gen_random_uuid(), :at)"), {"at": now}
        )
        # a technical partition from 2 months ago is beyond 30 days, a business one is within 24 months
        month = (now.replace(day=1) - timedelta(days=45)).replace(day=1)
        next_month = (month + timedelta(days=32)).replace(day=1)
        for klass in ("business", "technical"):
            await conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS events.events_{klass}_p{month:%Y%m} "
                    f"PARTITION OF events.events_{klass} "
                    f"FOR VALUES FROM ('{month:%Y-%m-%d}') TO ('{next_month:%Y-%m-%d}')"
                )
            )
    engine = RetentionEngine(
        ev.full.database,
        ev.publisher,
        registry=registry,
        config=ev.full.privacy.config,
        clock=FixedClock(datetime.now(UTC)),
    )
    outcomes = {o.target: o for o in await engine.run()}
    assert outcomes["events.business"].rows == 1  # only the 2020 business partition
    assert outcomes["events.technical"].rows == 2  # 2020 and two months ago
    assert outcomes["events.dedup_keys"].rows == 1
    async with ev.full.database.engine.connect() as conn:
        tables = set(
            (
                await conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'events' AND tablename LIKE 'events_%'"
                    )
                )
            ).scalars()
        )
    assert f"events_business_p{month:%Y%m}" in tables and f"events_technical_p{month:%Y%m}" not in tables
