"""Shared helpers for job/outbox integration tests."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from portalab.core.db import Database
from portalab.core.jobs.models import Job
from portalab.core.jobs.queue import enqueue
from portalab.core.time import FixedClock

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def clock() -> FixedClock:
    return FixedClock(T0)


async def add_job(db: Database, clk: FixedClock, **kwargs: Any) -> Any:
    kwargs.setdefault("kind", "demo.noop")
    kwargs.setdefault("payload", {})
    async with db.unit_of_work() as uow:
        return await enqueue(uow.session, clock=clk, **kwargs)


async def all_jobs(db: Database) -> list[Job]:
    async with db.session() as session:
        return list((await session.execute(select(Job).order_by(Job.created_at, Job.id))).scalars())
