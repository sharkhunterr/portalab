"""Generic, registry-driven privacy participants (T024; R6, spec 002 R11).

``RegistryErasureParticipant`` scrubs the personal-data columns classified in the kernel registry for the
rows owned by a user: nullable columns become NULL, NOT NULL ones take their tombstone value; the matching
user column, primary keys and foreign keys are kept so integrity and history survive. Append-only tables
are refused (they must not hold personal data, R5). ``RegistryExportContributor`` exports those same
columns, never anything unclassified (credentials, token hashes).
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Table, select

from portalab.capabilities.privacy_participants import (
    ERASURE_CAPABILITY,
    EXPORT_CAPABILITY,
    ErasureMode,
    ExportRecord,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import Database
from portalab.core.privacy_registry import personal_columns
from portalab.core.tombstone import scrub


def _check(table: Table, user_column: str) -> None:
    if table.info.get("portalab_append_only") == APPEND_ONLY_INFO["portalab_append_only"]:
        raise ValueError(f"{table.fullname} is append-only: it must not hold personal data")
    if user_column not in table.c:
        raise ValueError(f"{table.fullname} has no column {user_column!r}")


class RegistryErasureParticipant:
    def __init__(self, database: Database, table: Table, user_column: str = "user_id") -> None:
        _check(table, user_column)
        self.database = database
        self.table = table
        self.user_column = user_column

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await scrub(uow.session, self.table, where=self.table.c[self.user_column] == user_id)


class RegistryExportContributor:
    def __init__(
        self, database: Database, table: Table, user_column: str = "user_id", category: str | None = None
    ) -> None:
        _check(table, user_column)
        self.database = database
        self.table = table
        self.user_column = user_column
        self.category = category or table.fullname

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        columns = [name for name in personal_columns(self.table) if name != self.user_column]
        if not columns:
            return []
        statement = select(*(self.table.c[name] for name in columns)).where(
            self.table.c[self.user_column] == user_id
        )
        async with self.database.session() as session:
            rows = (await session.execute(statement)).mappings().all()
        return [
            ExportRecord(self.category, {key: _plain(value) for key, value in row.items()}) for row in rows
        ]


def _plain(value: Any) -> Any:
    return str(value) if isinstance(value, UUID) else value


def register_registry_participants(
    registry: CapabilityRegistry,
    database: Database,
    table: Table,
    *,
    user_column: str = "user_id",
    owner: str,
) -> None:
    """Opt a mapped table into generic erasure and export."""
    ref = f"registry:{table.fullname}"
    registry.provide(
        ERASURE_CAPABILITY,
        RegistryErasureParticipant(database, table, user_column),
        instance_ref=ref,
        owner=owner,
    )
    registry.provide(
        EXPORT_CAPABILITY,
        RegistryExportContributor(database, table, user_column),
        instance_ref=ref,
        owner=owner,
    )
