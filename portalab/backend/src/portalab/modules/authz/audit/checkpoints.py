"""Hash-chained audit checkpoints (T020; spec 021 R7).

A checkpoint covers the entries of a ``seq`` range: ``batch_hash`` hashes their canonical serialization in
``seq`` order and ``checkpoint_hash = sha256(prev_checkpoint_hash | from | to | count | batch_hash)``. Only
entries received more than ``SETTLE`` ago are covered, so a transaction still in flight cannot commit a
lower ``seq`` inside an already-sealed range. Chaining checkpoints (not rows) avoids write contention.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.authz.models import AuditCheckpoint, AuditEntry

GENESIS = "0" * 64
SETTLE = timedelta(minutes=5)
MAX_BATCH = 10_000


def entry_digest(entry: AuditEntry) -> str:
    parts = [
        str(entry.seq),
        str(entry.id),
        entry.occurred_at.isoformat(),
        entry.received_at.isoformat(),
        str(entry.actor_user_id or ""),
        entry.actor_kind,
        str(entry.acting_for or ""),
        entry.action,
        entry.resource_type or "",
        entry.resource_id or "",
        entry.scope or "",
        entry.decision,
        entry.result,
        json.dumps(entry.context, sort_keys=True, separators=(",", ":"), default=str),
        entry.correlation_id or "",
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def batch_hash(entries: list[AuditEntry]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry_digest(entry).encode("ascii"))
    return digest.hexdigest()


def chain_hash(prev: str, from_seq: int, to_seq: int, count: int, batch: str) -> str:
    return hashlib.sha256(f"{prev}|{from_seq}|{to_seq}|{count}|{batch}".encode("ascii")).hexdigest()


async def entries_between(session: AsyncSession, from_seq: int, to_seq: int) -> list[AuditEntry]:
    return list(
        (
            await session.execute(
                select(AuditEntry)
                .where(AuditEntry.seq >= from_seq, AuditEntry.seq <= to_seq)
                .order_by(AuditEntry.seq)
            )
        ).scalars()
    )


@dataclass(frozen=True, slots=True)
class CheckpointResult:
    checkpoint_id: int
    from_seq: int
    to_seq: int
    count: int


async def create_checkpoint(
    database: Database, events: EventPublisher, *, clock: Clock | None = None, now: datetime | None = None
) -> CheckpointResult | None:
    now = now or utc_now(clock)
    async with database.unit_of_work() as uow:
        session = uow.session
        last = (
            await session.execute(select(AuditCheckpoint).order_by(AuditCheckpoint.to_seq.desc()).limit(1))
        ).scalar_one_or_none()
        start = last.to_seq + 1 if last else await session.scalar(select(func.min(AuditEntry.seq)))
        if start is None:
            return None
        end = await session.scalar(
            select(func.max(AuditEntry.seq)).where(
                AuditEntry.seq >= start, AuditEntry.received_at < now - SETTLE
            )
        )
        if end is None:
            return None
        end = min(end, start + MAX_BATCH - 1)
        entries = await entries_between(session, start, end)
        batch = batch_hash(entries)
        prev = last.checkpoint_hash if last else GENESIS
        checkpoint = AuditCheckpoint(
            from_seq=start,
            to_seq=end,
            entry_count=len(entries),
            batch_hash=batch,
            prev_checkpoint_hash=prev,
            checkpoint_hash=chain_hash(prev, start, end, len(entries), batch),
            created_at=now,
        )
        session.add(checkpoint)
        await session.flush()
        await events.publish(
            session,
            "audit.checkpoint_created",
            {"from_seq": start, "to_seq": end, "count": len(entries)},
            occurred_at=now,
            source="audit",
            dedup_key=f"audit.checkpoint:{start}:{end}",
        )
        return CheckpointResult(checkpoint.id, start, end, len(entries))
