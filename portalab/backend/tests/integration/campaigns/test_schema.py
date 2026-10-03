"""014 T005 — schema: tables; append-only ``versions`` and ``activation_log``; the exclusion constraint
rejects overlapping intervals of a campaign; a single open interval per campaign; FKs only intra-module or
to ``identity.users``."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from tests.integration.campaigns.conftest import CampHarness

pytestmark = pytest.mark.integration


async def test_schema_and_constraints(cm: CampHarness) -> None:
    campaign = await cm.create()
    async with cm.database.session() as session:
        tables = set(
            (
                await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'campaigns'"))
            ).scalars()
        )
        foreign = set(
            (
                await session.execute(
                    text(
                        "SELECT confrelid::regclass::text FROM pg_constraint c JOIN pg_namespace n "
                        "ON n.oid = c.connamespace WHERE n.nspname = 'campaigns' AND contype = 'f'"
                    )
                )
            ).scalars()
        )
    assert {
        "campaigns",
        "versions",
        "occurrences",
        "activation_log",
        "open_intervals",
        "overrides",
        "attribute_failures",
    } <= tables
    assert all(f == "identity.users" or f.startswith("campaigns.") for f in foreign)
    insert = (
        "INSERT INTO campaigns.activation_log (id, campaign_id, version, during, cause) VALUES "
        "(gen_random_uuid(), :c, 1, tstzrange(:a, :b, '[)'), 'manual')"
    )
    async with cm.database.unit_of_work() as uow:
        await uow.session.execute(
            text(insert),
            {"c": campaign, "a": datetime(2026, 1, 1, tzinfo=UTC), "b": datetime(2026, 1, 2, tzinfo=UTC)},
        )
    async with cm.database.session() as session:
        with pytest.raises(Exception, match="ex_activation_log_overlap"):
            await session.execute(
                text(insert),
                {
                    "c": campaign,
                    "a": datetime(2026, 1, 1, 12, tzinfo=UTC),
                    "b": datetime(2026, 1, 3, tzinfo=UTC),
                },
            )
    for statement in ("UPDATE campaigns.versions SET version = 9", "DELETE FROM campaigns.activation_log"):
        async with cm.database.session() as session:
            with pytest.raises(Exception, match="append-only"):
                await session.execute(text(statement))
    open_row = (
        "INSERT INTO campaigns.open_intervals (campaign_id, version, opened_at, cause) "
        "VALUES (:c, 1, now(), 'manual')"
    )
    async with cm.database.session() as session:
        await session.execute(text(open_row), {"c": campaign})
        with pytest.raises(Exception, match=r"pk_open_intervals|duplicate"):
            await session.execute(text(open_row), {"c": campaign})
