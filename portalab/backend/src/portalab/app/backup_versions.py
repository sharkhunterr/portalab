"""Issue 247 — which schema a backup was saved with, compared with this portal's (the migrations' tree).

* **same** — the archive is loaded as it is;
* **older** — saved by a previous version: this new portal is first brought back to the archive's schema
  (its schemas dropped, then migrated up to the archive's revisions), the data loaded, then migrated up to
  this version as any portal is upgraded — each migration also transforms the data it changes;
* **newer** — saved by a version this one does not know (revisions missing from its migrations): refused,
  this portal is to be updated first.
"""

import asyncio
from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from portalab.app.migrations import current_heads, script, upgrade
from portalab.core.db import Database

Compatibility = Literal["same", "older", "newer"]


def portalab_version() -> str:
    try:
        return version("portalab")
    except PackageNotFoundError:
        return "unknown"


class SchemaVersions:
    def __init__(self, database: Database, database_url: str) -> None:
        self.database = database
        self.url = database_url

    async def current(self) -> set[str]:
        return await current_heads(self.database)

    async def compare(self, archive_heads: Iterable[str]) -> Compatibility:
        saved = set(archive_heads)
        mine = await self.current()
        if saved == mine:
            return "same"
        tree = script()
        known = {revision.revision for revision in tree.walk_revisions()}
        if not saved <= known:
            return "newer"  # revisions this version has never heard of
        applied = {
            revision.revision
            for revision in tree.revision_map.iterate_revisions(
                tuple(mine), "base", select_for_downgrade=True
            )
        }
        return "older" if saved <= applied else "newer"

    async def prepare(self, archive_heads: Iterable[str]) -> None:
        """Bring this (new, empty) portal back to the archive's schema: drop, then migrate up to it."""
        async with self.database.engine.begin() as conn:
            schemas = (
                await conn.exec_driver_sql(
                    "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\\_%' "
                    "AND nspname NOT IN ('information_schema', 'public')"
                )
            ).scalars()
            for schema in list(schemas):
                await conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        for head in sorted(archive_heads):
            await asyncio.to_thread(upgrade, self.url, head)
        await self.database.engine.dispose()  # no connection keeps plans of the dropped tables

    async def finish(self) -> None:
        """Migrate up to this version (the data loaded at the archive's schema transformed on the way)."""
        await asyncio.to_thread(upgrade, self.url)
        await self.database.engine.dispose()
