"""Execution history (T010, T027): per automation, newest first, references only (trigger ref, condition
trace, step outcomes) — never payload bodies or secrets; retention purge."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.models import DedupWindow, Execution, PendingFire


class History:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def list(
        self,
        automation_id: UUID,
        *,
        status: str | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[Execution]:
        statement = select(Execution).where(Execution.automation_id == automation_id)
        if status:
            statement = statement.where(Execution.status == status)
        if before:
            statement = statement.where(Execution.started_at < before)
        async with self.database.session() as session:
            rows = await session.execute(
                statement.order_by(Execution.started_at.desc(), Execution.id.desc()).limit(
                    max(1, min(limit, 200))
                )
            )
            return list(rows.scalars())

    async def get(self, execution_id: UUID) -> Execution | None:
        async with self.database.session() as session:
            return await session.get(Execution, execution_id)

    async def purge(self, retention_days: int) -> int:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            executions = await uow.session.execute(
                delete(Execution).where(
                    Execution.started_at < now - timedelta(days=max(1, retention_days)),
                    Execution.status != "awaiting_approval",
                )
            )
            await uow.session.execute(delete(DedupWindow).where(DedupWindow.expires_at < now))
            await uow.session.execute(
                delete(PendingFire).where(
                    PendingFire.fired.is_(True), PendingFire.fire_at < now - timedelta(days=7)
                )
            )
        return int(getattr(executions, "rowcount", 0) or 0)
