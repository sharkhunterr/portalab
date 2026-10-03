"""``HistoryProjection`` (T024; R8, R9, FR-017..019): the 007 event stream is the record; this consumer
derives ``history_entries`` (one per event id — replays and redeliveries are no-ops) and ``user_progress``:

* resume point and percent follow the event with the greatest ``occurred_at`` across **all** sources;
* ``finished`` is sticky — older or later progress never turns a finished object back to in-progress;
* an abandoned session past 5 % of a still-unfinished object emits ``media.resume_available`` (live only,
  never during a replay).
Rebuilding from the event log reproduces the same rows."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import HistoryEntry, MediaObject, UserProgress

CONSUMER = "media.history"
OWNER = "module:media"
TYPES = frozenset(
    {
        "media.playback_progressed",
        "media.playback_paused",
        "media.playback_finished",
        "media.playback_abandoned",
    }
)
RESUME_FLOOR = 0.05


class HistoryProjection:
    def __init__(self, database: Database, events: EventPublisher, *, clock: Clock | None = None) -> None:
        self.database = database
        self.events = events
        self.clock = clock

    def consumer(self) -> Consumer:
        return Consumer(CONSUMER, TYPES, self.handle, OWNER, replay_safe=True)

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        payload = dict(envelope.payload)
        if (
            envelope.type not in TYPES
            or envelope.subject_type != "user"
            or not envelope.subject_id
            or not payload.get("object")
        ):
            return
        await self.apply(
            event_id=envelope.event_id,
            event_type=envelope.type,
            user=UUID(envelope.subject_id),
            object_id=UUID(str(payload["object"])),
            payload=payload,
            occurred_at=envelope.occurred_at,
            live=not ctx.replay,
        )

    async def apply(
        self,
        *,
        event_id: UUID,
        event_type: str,
        user: UUID,
        object_id: UUID,
        payload: dict[str, Any],
        occurred_at: datetime,
        live: bool,
    ) -> bool:
        position = float(payload.get("position_s") or 0.0)
        duration = payload.get("duration_s")
        share = payload.get("percent")
        if share is None and duration:
            share = min(1.0, position / float(duration))
        finished = event_type == "media.playback_finished"
        kind = (
            "finished"
            if finished
            else ("session" if event_type == "media.playback_abandoned" else "progress")
        )
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if await session.get(MediaObject, object_id) is None:
                return False
            previous = (
                await session.execute(
                    select(HistoryEntry.position_to_s)
                    .where(HistoryEntry.session_key == payload.get("session"), HistoryEntry.user_id == user)
                    .order_by(HistoryEntry.occurred_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            start = float(previous) if previous is not None else 0.0
            inserted = (
                await session.execute(
                    insert(HistoryEntry)
                    .values(
                        event_id=event_id,
                        user_id=user,
                        object_id=object_id,
                        kind=kind,
                        source_system=str(payload.get("service", "")),
                        session_key=payload.get("session"),
                        position_from_s=start,
                        position_to_s=position,
                        consumed_s=max(0.0, position - start),
                        completed=finished,
                        occurred_at=occurred_at,
                        received_at=utc_now(self.clock),
                    )
                    .on_conflict_do_nothing(constraint="uq_history_entries_event")
                    .returning(HistoryEntry.id)
                )
            ).scalar_one_or_none()
            if inserted is None:
                return False  # already applied (replay, redelivery)
            progress = await self._progress(session, user, object_id, position, share, finished, occurred_at)
            if (
                live
                and event_type == "media.playback_abandoned"
                and progress.state != "finished"
                and (share or 0) >= RESUME_FLOOR
            ):
                await self.events.publish(
                    session,
                    "media.resume_available",
                    {
                        "object": str(object_id),
                        "kind": str(payload.get("kind", "")),
                        "percent": float(share or 0),
                    },
                    occurred_at=occurred_at,
                    subject=SubjectRef("user", str(user)),
                    source="media",
                    dedup_key=f"media.resume:{payload.get('session')}",
                )
        return True

    async def _progress(
        self,
        session: AsyncSession,
        user: UUID,
        object_id: UUID,
        position: float,
        share: float | None,
        finished: bool,
        occurred_at: datetime,
    ) -> UserProgress:
        row = await session.get(UserProgress, (user, object_id), with_for_update=True)
        if row is None:
            row = UserProgress(
                user_id=user,
                object_id=object_id,
                resume_position_s=0.0 if finished else position,
                percent=1.0 if finished else float(share or 0.0),
                state="finished" if finished else "in_progress",
                last_occurred_at=occurred_at,
                finished_at=occurred_at if finished else None,
            )
            session.add(row)
            return row
        if finished and row.state != "finished":
            row.state, row.finished_at, row.percent = "finished", occurred_at, 1.0
        if occurred_at >= row.last_occurred_at:
            row.last_occurred_at = occurred_at
            if row.state != "finished":
                row.resume_position_s, row.percent = position, float(share or 0.0)
        elif finished and row.finished_at and occurred_at < row.finished_at:
            row.finished_at = occurred_at
        return row

    async def history(
        self, user: UUID, *, limit: int = 50, before: datetime | None = None
    ) -> list[tuple[HistoryEntry, MediaObject]]:
        async with self.database.session() as session:
            stmt = (
                select(HistoryEntry, MediaObject)
                .join(MediaObject, MediaObject.id == HistoryEntry.object_id)
                .where(HistoryEntry.user_id == user, HistoryEntry.kind != "progress")
                .order_by(HistoryEntry.occurred_at.desc())
                .limit(limit)
            )
            if before is not None:
                stmt = stmt.where(HistoryEntry.occurred_at < before)
            return [(h, o) for h, o in (await session.execute(stmt)).all()]

    async def continue_items(self, user: UUID, *, limit: int = 20) -> list[tuple[UserProgress, MediaObject]]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(UserProgress, MediaObject)
                .join(MediaObject, MediaObject.id == UserProgress.object_id)
                .where(
                    UserProgress.user_id == user,
                    UserProgress.state == "in_progress",
                    UserProgress.percent >= RESUME_FLOOR,
                    MediaObject.status == "active",
                )
                .order_by(UserProgress.last_occurred_at.desc())
                .limit(limit)
            )
            return [(p, o) for p, o in rows.all()]

    async def recompute(self, session: AsyncSession, users: set[UUID]) -> None:
        """Progress derived again from history (after a merge/split moved entries between objects)."""
        for user in users:
            await session.execute(delete(UserProgress).where(UserProgress.user_id == user))
            entries = (
                (
                    await session.execute(
                        select(HistoryEntry)
                        .where(HistoryEntry.user_id == user)
                        .order_by(HistoryEntry.occurred_at)
                    )
                )
                .scalars()
                .all()
            )
            for entry in entries:
                await session.flush()
                await self._progress(
                    session,
                    user,
                    entry.object_id,
                    entry.position_to_s,
                    None if not entry.completed else 1.0,
                    entry.completed,
                    entry.occurred_at,
                )
