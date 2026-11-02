"""``HistoryProjection`` (T024; R8, R9, FR-017..019): the 007 event stream is the record; this consumer
derives ``history_entries`` (one per event id — replays and redeliveries are no-ops) and ``user_progress``:

* resume point and percent follow the event with the greatest ``occurred_at`` across **all** sources;
* ``finished`` is sticky — older or later progress never turns a finished object back to in-progress;
* an abandoned session past 5 % of a still-unfinished object emits ``media.resume_available`` (live only,
  never during a replay);
* issue 234: the last episode of a season finished (every episode of it in the library finished) emits
  ``media.season_finished`` — once per member and season, live only.
Rebuilding from the event log reproduces the same rows."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
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
BOOK_KINDS = ("book", "audiobook")


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
            was_finished = await self._finished(session, user, object_id)
            progress = await self._progress(session, user, object_id, position, share, finished, occurred_at)
            if live and finished and not was_finished:
                await self._season(session, user, object_id, occurred_at)
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

    async def _finished(self, session: AsyncSession, user: UUID, object_id: UUID) -> bool:
        state = await session.scalar(
            select(UserProgress.state).where(
                UserProgress.user_id == user, UserProgress.object_id == object_id
            )
        )
        return state == "finished"

    async def _season(self, session: AsyncSession, user: UUID, episode: UUID, occurred_at: datetime) -> None:
        """Issue 234: an episode finished — its season too when every episode of it is (#343: at its last
        episode's finish)."""
        item = await session.get(MediaObject, episode)
        if item is None or item.kind != "episode" or item.parent_id is None:
            return
        season = await session.get(MediaObject, item.parent_id)
        if season is None or season.kind != "season":
            return
        await session.flush()
        episodes = list(
            (
                await session.execute(
                    select(MediaObject.id).where(
                        MediaObject.parent_id == season.id, MediaObject.kind == "episode"
                    )
                )
            ).scalars()
        )
        done, last = (
            await session.execute(
                select(func.count(), func.max(UserProgress.finished_at)).where(
                    UserProgress.user_id == user,
                    UserProgress.object_id.in_(episodes),
                    UserProgress.state == "finished",
                )
            )
        ).one()
        if not episodes or int(done or 0) < len(episodes):
            return
        # #343: finished when its last episode was — however late, and in whatever order, they are told
        occurred_at = last or occurred_at
        await self.events.publish(
            session,
            "media.season_finished",
            {
                "object": str(season.id),
                "kind": "season",
                "series": str(season.parent_id) if season.parent_id else None,
                "episodes": len(episodes),
            },
            occurred_at=occurred_at,
            subject=SubjectRef("user", str(user)),
            source="media",
            dedup_key=f"media.season_finished:{season.id}:{user}",
        )

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
                    # #20, #21: a book or an audiobook is « under way » from its first page or minute (a few
                    # percent of a long audiobook are already hours); a film from 5 %
                    or_(
                        UserProgress.percent >= RESUME_FLOOR,
                        and_(MediaObject.kind.in_(BOOK_KINDS), UserProgress.percent > 0),
                    ),
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
