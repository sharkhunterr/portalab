"""Contribution ledger (T016; R7): every registration a plugin makes through its context is recorded
(point, id, priority, state). Conflicts are recorded as ``conflict`` (the earlier owner keeps the slot —
deterministic by ``(priority, plugin key, id)`` at load) and shown in diagnostics. Removal marks the rows
``removed`` after the registries are swept."""

from datetime import datetime

from sqlalchemy import select, update

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins.models import Contribution


class Ledger:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def record(
        self,
        plugin: str,
        point: str,
        contribution_id: str,
        *,
        priority: int = 100,
        state: str = "active",
        detail: str | None = None,
    ) -> None:
        async with self.database.unit_of_work() as uow:
            uow.session.add(
                Contribution(
                    plugin_key=plugin,
                    point=point,
                    contribution_id=contribution_id[:200],
                    state=state,
                    priority=priority,
                    detail=(detail or None) and detail[:300],
                    registered_at=utc_now(self.clock),
                )
            )

    async def removed(self, plugin: str, at: datetime | None = None) -> int:
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(
                update(Contribution)
                .where(Contribution.plugin_key == plugin, Contribution.state != "removed")
                .values(state="removed", removed_at=at or utc_now(self.clock))
            )
        return int(getattr(result, "rowcount", 0) or 0)

    async def entries(self, plugin: str, *, active_only: bool = False) -> list[Contribution]:
        statement = select(Contribution).where(Contribution.plugin_key == plugin)
        if active_only:
            statement = statement.where(Contribution.state != "removed")
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(statement.order_by(Contribution.registered_at, Contribution.point))
                ).scalars()
            )
