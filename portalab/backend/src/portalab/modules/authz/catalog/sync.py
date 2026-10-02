"""Lazy, once-per-process catalog synchronisation.

The API may start before migrations ran (``/readyz`` stays 503 until they did), so the catalog is synced on
first use instead of at import time, and re-attempted until it succeeds. ``portalab migrate`` also syncs it.
"""

import asyncio

from portalab.core.db import Database
from portalab.core.permissions import PermissionRegistry, default_permissions
from portalab.core.time import Clock
from portalab.modules.authz.catalog.declare import sync_catalog


class CatalogSync:
    def __init__(
        self,
        database: Database,
        registry: PermissionRegistry = default_permissions,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.registry = registry
        self.clock = clock
        self._done = False
        self._lock = asyncio.Lock()

    async def ensure(self) -> None:
        if self._done:
            return
        async with self._lock:
            if not self._done:
                await self.sync()

    async def sync(self) -> int:
        async with self.database.unit_of_work() as uow:
            created = await sync_catalog(uow.session, self.registry, self.clock)
        self._done = True
        return created

    def invalidate(self) -> None:
        """Force a re-sync (a plugin registered or withdrew permissions)."""
        self._done = False
