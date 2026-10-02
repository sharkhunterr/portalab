"""Monthly range partitions for append-only stores (spec 021 R5/R7).

Partitions are named ``<table>_pYYYYMM`` and cover ``[month, next month)`` of the partition key; a
``<table>_pdefault`` partition catches anything outside. Retention removes whole partitions (``DROP TABLE``)
so row-level UPDATE/DELETE stays impossible on append-only tables.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _check(identifier: str) -> str:
    if not _IDENT.fullmatch(identifier):
        raise ValueError(f"invalid SQL identifier {identifier!r}")
    return identifier


@dataclass(frozen=True, slots=True)
class MonthPartition:
    name: str
    month: date

    @property
    def end(self) -> date:
        return next_month(self.month)


def month_start(value: datetime | date) -> date:
    return date(value.year, value.month, 1)


def next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


async def month_partitions(session: AsyncSession, schema: str, table: str) -> list[MonthPartition]:
    schema, table = _check(schema), _check(table)
    rows = await session.execute(
        text(
            "SELECT child.relname FROM pg_inherits "
            "JOIN pg_class parent ON pg_inherits.inhparent = parent.oid "
            "JOIN pg_class child ON pg_inherits.inhrelid = child.oid "
            "JOIN pg_namespace ns ON parent.relnamespace = ns.oid "
            "WHERE ns.nspname = :schema AND parent.relname = :table"
        ),
        {"schema": schema, "table": table},
    )
    partitions = []
    pattern = re.compile(rf"^{re.escape(table)}_p(\d{{4}})(\d{{2}})$")
    for (name,) in rows:
        match = pattern.fullmatch(name)
        if match:
            partitions.append(MonthPartition(name, date(int(match.group(1)), int(match.group(2)), 1)))
    return sorted(partitions, key=lambda partition: partition.month)


async def ensure_month_partitions(
    session: AsyncSession, schema: str, table: str, now: datetime, months_ahead: int = 2
) -> list[str]:
    """Create the current and ``months_ahead`` next partitions when missing; returns the created names."""
    schema, table = _check(schema), _check(table)
    existing = {partition.month for partition in await month_partitions(session, schema, table)}
    created = []
    month = month_start(now)
    for _ in range(months_ahead + 1):
        if month not in existing:
            name = f"{table}_p{month:%Y%m}"
            await session.execute(
                text(
                    f'CREATE TABLE "{schema}"."{name}" PARTITION OF "{schema}"."{table}" '
                    f"FOR VALUES FROM ('{month.isoformat()}') TO ('{next_month(month).isoformat()}')"
                )
            )
            created.append(name)
        month = next_month(month)
    return created


async def drop_month_partitions_before(
    session: AsyncSession, schema: str, table: str, cutoff: datetime
) -> list[str]:
    """Drop every monthly partition entirely older than ``cutoff`` (its end ≤ cutoff)."""
    schema = _check(schema)
    limit = cutoff.astimezone(UTC).date()
    dropped = []
    for partition in await month_partitions(session, schema, table):
        if partition.end <= limit:
            await session.execute(text(f'DROP TABLE "{schema}"."{partition.name}"'))
            dropped.append(partition.name)
    return dropped
