"""The intrusion guard's blocks in the database (spec 028 FR-040): every process sees the same ones, a restart
keeps them, the console lifts them."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select, update

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.identity.models import SecurityBlock


@dataclass(frozen=True, slots=True)
class ActiveBlock:
    id: UUID
    kind: str  # account | session | address
    subject: str
    label: str | None
    reason: str
    points: int
    paths: list[str]
    started_at: datetime
    until: datetime


class BlockStore:
    def __init__(self, database: Database, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def record(
        self,
        kind: str,
        subject: str,
        *,
        reason: str,
        seconds: float,
        label: str | None = None,
        points: int = 0,
        paths: Iterable[str] = (),
    ) -> UUID:
        now = utc_now(self.clock)
        row = SecurityBlock(
            kind=kind,
            subject=subject[:128],
            label=(label or None) and label[:128],
            reason=reason[:64],
            points=points,
            paths=[p[:200] for p in list(paths)[-8:]],
            started_at=now,
            until=now + timedelta(seconds=seconds),
        )
        async with self.database.unit_of_work() as uow:
            uow.session.add(row)
            await uow.session.flush()
            return row.id

    async def active(self) -> list[ActiveBlock]:
        now = utc_now(self.clock)
        async with self.database.session() as session:
            rows = await session.execute(
                select(SecurityBlock)
                .where(SecurityBlock.lifted_at.is_(None), SecurityBlock.until > now)
                .order_by(SecurityBlock.started_at)
            )
            return [
                ActiveBlock(
                    r.id, r.kind, r.subject, r.label, r.reason, r.points, list(r.paths), r.started_at, r.until
                )
                for r in rows.scalars()
            ]

    async def lift(self, *, by: str, block: UUID | None = None, subject: str | None = None) -> int:
        """Lifts one block (by id), the blocks of a subject (a login, a user id or an address), or every
        active one; returns how many."""
        now = utc_now(self.clock)
        query = update(SecurityBlock).where(SecurityBlock.lifted_at.is_(None), SecurityBlock.until > now)
        if block is not None:
            query = query.where(SecurityBlock.id == block)
        elif subject is not None:
            query = query.where(or_(SecurityBlock.subject == subject, SecurityBlock.label == subject))
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(query.values(lifted_at=now, lifted_by=by[:128]))
            return int(result.rowcount or 0)  # type: ignore[attr-defined]
