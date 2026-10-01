"""Job queue / transactional outbox (plan §6, research R6).

* :func:`enqueue` runs **in the caller's transaction** so publishing is atomic with the state change;
* :func:`claim` uses ``FOR UPDATE SKIP LOCKED`` (concurrent workers never take the same job) and re-claims
  ``running`` jobs whose lock expired (crash recovery);
* delivery is at-least-once: handlers must be idempotent (keyed per CD-012 by the event model of spec 007);
* the deduplication key is never a bare timestamp (CD-012).
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.db import Database
from portalab.core.ids import new_id
from portalab.core.jobs.models import Job
from portalab.core.logging import get_correlation_id, is_secret_key, redact_text
from portalab.core.time import Clock, require_aware, utc_now

DEFAULT_QUEUE = "default"
DEFAULT_LOCK_SECONDS = 300
MAX_ERROR_LENGTH = 2000
BASE_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 3600

_TIMESTAMP_ONLY = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?|\d{9,}(\.\d+)?)\s*$"
)


@dataclass(frozen=True, slots=True)
class EnqueueResult:
    job_id: UUID
    created: bool


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: UUID
    queue: str
    kind: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    correlation_id: str | None


def backoff_seconds(attempt: int) -> int:
    """Delay before retry number ``attempt`` (1-based): 5s, 10s, 20s, … capped at one hour."""
    return int(min(BASE_BACKOFF_SECONDS * 2 ** max(attempt - 1, 0), MAX_BACKOFF_SECONDS))


def check_payload(payload: Any, path: str = "payload") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if is_secret_key(str(key)):
                raise ValueError(f"{path}.{key}: job payloads must reference ids, never carry secrets")
            check_payload(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            check_payload(value, f"{path}[{index}]")


def _check_dedup_key(dedup_key: str | None) -> None:
    if dedup_key is None:
        return
    if not dedup_key.strip():
        raise ValueError("dedup_key must not be empty")
    if _TIMESTAMP_ONLY.match(dedup_key):
        raise ValueError("dedup_key must not be a timestamp alone (CD-012): use a source id or event context")


async def enqueue(
    session: AsyncSession,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
    queue: str = DEFAULT_QUEUE,
    dedup_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int = 5,
    clock: Clock | None = None,
) -> EnqueueResult:
    """Insert a job in the caller's transaction; a duplicate ``(queue, dedup_key)`` is a no-op."""
    payload = dict(payload or {})
    check_payload(payload)
    _check_dedup_key(dedup_key)
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    now = utc_now(clock)
    job_id = new_id()
    values = {
        "id": job_id,
        "queue": queue,
        "kind": kind,
        "payload": payload,
        "dedup_key": dedup_key,
        "status": "queued",
        "run_at": require_aware(run_at) if run_at else now,
        "attempts": 0,
        "max_attempts": max_attempts,
        "correlation_id": get_correlation_id(),
        "created_at": now,
        "updated_at": now,
    }
    statement = insert(Job).values(**values)
    if dedup_key is not None:
        statement = statement.on_conflict_do_nothing(
            index_elements=[Job.queue, Job.dedup_key], index_where=Job.dedup_key.is_not(None)
        )
    inserted = (await session.execute(statement.returning(Job.id))).scalar_one_or_none()
    if inserted is not None:
        return EnqueueResult(job_id=inserted, created=True)
    existing = await session.execute(select(Job.id).where(Job.queue == queue, Job.dedup_key == dedup_key))
    return EnqueueResult(job_id=existing.scalar_one(), created=False)


async def claim(
    database: Database,
    *,
    queue: str = DEFAULT_QUEUE,
    worker_id: str,
    limit: int = 1,
    lock_seconds: int = DEFAULT_LOCK_SECONDS,
    clock: Clock | None = None,
) -> list[ClaimedJob]:
    """Atomically lock up to ``limit`` due jobs (queued, or running with an expired lock)."""
    now = utc_now(clock)
    async with database.unit_of_work() as uow:
        due = (
            select(Job)
            .where(
                Job.queue == queue,
                or_(
                    and_(Job.status == "queued", Job.run_at <= now),
                    and_(Job.status == "running", Job.locked_until < now),
                ),
            )
            .order_by(Job.run_at, Job.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list((await uow.session.execute(due)).scalars())
        claimed: list[ClaimedJob] = []
        for job in jobs:
            job.status = "running"
            job.locked_by = worker_id
            job.locked_until = now + timedelta(seconds=lock_seconds)
            job.attempts += 1
            job.updated_at = now
            claimed.append(
                ClaimedJob(
                    id=job.id,
                    queue=job.queue,
                    kind=job.kind,
                    payload=dict(job.payload),
                    attempts=job.attempts,
                    max_attempts=job.max_attempts,
                    correlation_id=job.correlation_id,
                )
            )
    return claimed


async def succeed(database: Database, job_id: UUID, *, worker_id: str, clock: Clock | None = None) -> bool:
    """Mark a job done; refused (False) if another worker took over the lock meanwhile."""
    now = utc_now(clock)
    async with database.unit_of_work() as uow:
        result = await uow.session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "running", Job.locked_by == worker_id)
            .values(status="succeeded", locked_by=None, locked_until=None, updated_at=now)
        )
    return bool(getattr(result, "rowcount", 0))


async def fail(
    database: Database, job_id: UUID, *, worker_id: str, error: str, clock: Clock | None = None
) -> str | None:
    """Back off and requeue, or mark ``dead`` after ``max_attempts``; returns the new status."""
    now = utc_now(clock)
    message = redact_text(error)[:MAX_ERROR_LENGTH]
    async with database.unit_of_work() as uow:
        job = (
            await uow.session.execute(
                select(Job)
                .where(Job.id == job_id, Job.status == "running", Job.locked_by == worker_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if job is None:
            return None
        job.last_error = message
        job.locked_by = None
        job.locked_until = None
        job.updated_at = now
        if job.attempts >= job.max_attempts:
            job.status = "dead"
        else:
            job.status = "queued"
            job.run_at = now + timedelta(seconds=backoff_seconds(job.attempts))
        return job.status
