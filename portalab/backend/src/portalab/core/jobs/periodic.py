"""Self-rescheduling periodic jobs on the PostgreSQL queue (no external scheduler).

A periodic handler runs, then enqueues its next run for the next slot; the dedup key ``<kind>:<slot>``
makes seeding idempotent (several workers, restarts), and is never a bare timestamp (CD-012).
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from portalab.core.db import Database
from portalab.core.jobs.queue import enqueue
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock, utc_now


def slot_of(at: datetime, interval: timedelta) -> datetime:
    seconds = int(interval.total_seconds())
    epoch = int(at.timestamp())
    return datetime.fromtimestamp(epoch - epoch % seconds, tz=at.tzinfo)


async def schedule(
    database: Database, kind: str, at: datetime, interval: timedelta, clock: Clock | None
) -> None:
    slot = slot_of(at, interval)
    async with database.unit_of_work() as uow:
        await enqueue(
            uow.session,
            kind=kind,
            dedup_key=f"{kind}:{slot.strftime('%Y%m%dT%H%M')}",
            run_at=slot,
            clock=clock,
        )


def register_periodic(
    registry: JobRegistry,
    database: Database,
    kind: str,
    interval: timedelta,
    func: Callable[[], Awaitable[Any]],
    *,
    owner: str,
    clock: Clock | None = None,
    timeout_seconds: float = 300,
) -> Callable[[], Awaitable[None]]:
    """Register ``kind`` and return a ``seed()`` coroutine function to call at worker start."""

    async def handler(payload: dict[str, Any]) -> None:
        await func()
        await schedule(database, kind, utc_now(clock) + interval, interval, clock)

    registry.register(
        kind,
        handler,
        idempotency="periodic sweep; each run is repeatable",
        timeout_seconds=timeout_seconds,
        owner=owner,
    )

    async def seed() -> None:
        await schedule(database, kind, utc_now(clock), interval, clock)

    return seed
