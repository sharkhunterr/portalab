"""Live progress of the media background tasks (027): a row per task — the history of one service
(``history:<service>``), the metadata enrichment (``metadata``) — read by the sources panel to show a
spinner while it runs and a progress bar when the total is known."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.core.db import Database
from portalab.modules.media.models import TaskProgress


def history_task(service_id: UUID | str) -> str:
    return f"history:{service_id}"


class Progress:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def set(
        self, task: str, at: datetime, *, running: bool, done: int | None = None, total: int | None = None
    ) -> None:
        values: dict[str, Any] = {"task": task, "updated_at": at, "done": done or 0, "total": total}
        values["running_since"] = at if running else None
        update: dict[str, Any] = {"updated_at": at}
        if done is not None:
            update["done"] = done
        if total is not None:
            update["total"] = total
        statement = insert(TaskProgress).values(values)
        if running:  # keep the first start time of a run in progress
            update["running_since"] = func.coalesce(TaskProgress.running_since, at)
        else:
            update["running_since"] = None
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(statement.on_conflict_do_update(index_elements=["task"], set_=update))

    async def all(self) -> dict[str, TaskProgress]:
        async with self.database.session() as session:
            return {row.task: row for row in (await session.execute(select(TaskProgress))).scalars()}
