"""Registry-driven anonymization (tombstone) — data-model.md §4, research R8.

Final deletion keeps rows and their ids (ledger/history integrity) and scrubs only the columns classified
as personal data in :mod:`portalab.core.privacy_registry`. Primary-key and foreign-key columns are never
scrubbed.
Nullable columns become NULL; NOT NULL columns take their declared tombstone value. No table name is
hard-coded: Privacy (spec 021) calls these helpers for every registered table.
"""

from typing import Any

from sqlalchemy import ColumnElement, Table, update
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.privacy_registry import TOMBSTONE_KEY, personal_columns


class TombstoneError(ValueError):
    """A NOT NULL personal-data column has no declared tombstone value."""


def scrub_values(table: Table) -> dict[str, Any]:
    """Column → replacement value for every scrub-able personal column of ``table``."""
    values: dict[str, Any] = {}
    for name in personal_columns(table):
        column = table.columns[name]
        if column.primary_key or column.foreign_keys:
            continue
        if column.nullable:
            values[name] = None
        elif TOMBSTONE_KEY in column.info:
            values[name] = column.info[TOMBSTONE_KEY]
        else:
            raise TombstoneError(
                f"{table.fullname}.{name} is NOT NULL personal data without a tombstone value"
            )
    return values


async def scrub(session: AsyncSession, table: Table, *, where: ColumnElement[bool]) -> int:
    """Scrub personal columns of the rows matching ``where``; returns the number of rows touched."""
    values = scrub_values(table)
    if not values:
        return 0
    result = await session.execute(update(table).where(where).values(**values))
    return int(getattr(result, "rowcount", 0) or 0)


async def tombstone(session: AsyncSession, table: Table, row_id: Any) -> int:
    """Scrub one row identified by its (single-column) primary key; idempotent."""
    primary = list(table.primary_key.columns)
    if len(primary) != 1:
        raise TombstoneError(f"{table.fullname} must have a single-column primary key to be tombstoned")
    return await scrub(session, table, where=primary[0] == row_id)
