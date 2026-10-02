"""021 T015 — audit entries land in monthly partitions; old partitions are dropped by retention;
row-level UPDATE/DELETE stay rejected."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from portalab.core.partitions import month_partitions
from portalab.modules.authz.audit.partitions import maintain, retention_cutoff
from tests.privacy_fixtures import FullPlatform

INSERT = text(
    "INSERT INTO audit.audit_entries (id, occurred_at, received_at, actor_kind, action, decision, result) "
    "VALUES (:id, :at, :at, 'system', 'test', 'n/a', 'n/a')"
)


async def _partition_of(full: FullPlatform, entry_id: object) -> str:
    async with full.database.engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT tableoid::regclass::text FROM audit.audit_entries WHERE id = :id"),
                {"id": entry_id},
            )
        ).scalar_one()


async def test_rows_land_in_monthly_partitions(full: FullPlatform) -> None:
    now = datetime.now(UTC)
    await maintain(full.database, now, retention_months=None)
    entry = uuid4()
    async with full.database.engine.begin() as conn:
        await conn.execute(INSERT, {"id": entry, "at": now})
    assert await _partition_of(full, entry) == f"audit.audit_entries_p{now:%Y%m}"


async def test_retention_drops_old_partitions_only(full: FullPlatform) -> None:
    old_month = datetime(2020, 3, 15, tzinfo=UTC)
    async with full.database.engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE audit.audit_entries_p202003 PARTITION OF audit.audit_entries "
                "FOR VALUES FROM ('2020-03-01') TO ('2020-04-01')"
            )
        )
        await conn.execute(INSERT, {"id": uuid4(), "at": old_month})
    now = datetime.now(UTC)
    result = await maintain(full.database, now, retention_months=24)
    assert "audit_entries_p202003" in result["dropped"]
    async with full.database.session() as session:
        months = [partition.month for partition in await month_partitions(session, "audit", "audit_entries")]
    assert all(month >= retention_cutoff(now, 24).date() for month in months)
    assert len(result["dropped"]) == 1


async def test_row_level_changes_still_rejected(full: FullPlatform) -> None:
    async with full.database.engine.begin() as conn:
        await conn.execute(INSERT, {"id": uuid4(), "at": datetime.now(UTC)})
    for statement in ("UPDATE audit.audit_entries SET action = 'x'", "DELETE FROM audit.audit_entries"):
        with pytest.raises(DBAPIError, match="append-only"):
            async with full.database.engine.begin() as conn:
                await conn.execute(text(statement))
