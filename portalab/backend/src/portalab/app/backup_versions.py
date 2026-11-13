"""Issue 247 — which schema a backup was saved with, compared with this portal's (the migrations' tree).

* **same** — the archive is loaded as it is;
* **older** — saved by a previous version: this new portal is first brought back to the archive's schema
  (its schemas dropped, then migrated up to the archive's revisions), the data loaded, then migrated up to
  this version as any portal is upgraded — each migration also transforms the data it changes;
* **newer** — saved by a version this one does not know (revisions missing from its migrations): refused,
  this portal is to be updated first.
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Literal

import portalab
from portalab.app.migrations import current_heads, script, upgrade
from portalab.core.db import Database
from portalab.modules.administration.backup.archive import ResetStep

Compatibility = Literal["same", "older", "newer"]


def portalab_version() -> str:
    # the source's own version — the installed package's metadata lags behind in a dev venv not re-synced
    return portalab.__version__


class SchemaVersions:
    def __init__(self, database: Database, database_url: str) -> None:
        self.database = database
        self.url = database_url
        # the built-in packs written again, each one told (done, total, pack)
        self.after_reset: Callable[[Callable[[int, int, str], None]], Awaitable[object]] | None = None

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

    async def _drop_everything(self, step: ResetStep | None = None) -> None:
        """Every schema of the portal dropped (and its plugins' roles): the database as on its first day."""
        async with self.database.engine.begin() as conn:
            schemas = list(
                (
                    await conn.exec_driver_sql(
                        "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\\_%' "
                        "AND nspname NOT IN ('information_schema', 'public') ORDER BY nspname"
                    )
                ).scalars()
            )
            for done, schema in enumerate(schemas):
                if step is not None:
                    step("schema.drop", done, len(schemas), schema)
                await conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        async with self.database.engine.begin() as conn:
            roles = list(
                (
                    await conn.exec_driver_sql("SELECT rolname FROM pg_roles WHERE rolname LIKE 'plugin\\_%'")
                ).scalars()
            )
        for role in roles:  # one by one: a role still owning objects elsewhere (another database) is kept
            try:
                async with self.database.engine.begin() as conn:
                    await conn.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
            except Exception:  # noqa: S112 — best effort
                continue

    async def prepare(self, archive_heads: Iterable[str]) -> None:
        """Bring this (new, empty) portal back to the archive's schema: drop, then migrate up to it."""
        await self._drop_everything()
        for head in sorted(archive_heads):
            await asyncio.to_thread(upgrade, self.url, head)
        await self.database.engine.dispose()  # no connection keeps plans of the dropped tables

    async def reset(self, step: ResetStep | None = None) -> None:
        """Issue 247: the portal back to a new installation — everything dropped, migrated again, its
        built-in catalogs (permissions, visual packs) written again, as ``portalab migrate`` does; each step
        told to ``step`` as it goes."""
        from portalab.app.cli import _sync_permission_catalog

        def tell(key: str, done: int = 0, total: int = 0, on: str | None = None) -> None:
            if step is not None:
                step(key, done, total, on)

        await self._drop_everything(step)
        tell("schema.create")
        await asyncio.to_thread(upgrade, self.url)
        await self.database.engine.dispose()
        tell("schema.permissions")
        await _sync_permission_catalog(self.url)
        if self.after_reset is not None:
            tell("schema.packs")
            await self.after_reset(lambda done, total, pack: tell("schema.packs", done, total, pack))

    async def finish(self) -> None:
        """Migrate up to this version (the data loaded at the archive's schema transformed on the way)."""
        await asyncio.to_thread(upgrade, self.url)
        await self.database.engine.dispose()
