"""#94 — a play the live watch missed still counts: when a service's history (Plex, Tautulli, Grimmory…)
records a member's play, ``media.playback_finished`` (at the kind's threshold) or
``media.playback_abandoned`` (stopped before, with the minutes watched) is published for it — the events
the progression rules, quests and the play streak listen to — unless the live watch saw that play end.
Only recent plays (``WINDOW``): an old history imported later never turns into XP, the progression stays
the one the portal lived."""

from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import Activity, PlaybackSession
from portalab.modules.media.observability import metrics
from portalab.modules.media.playback.normalizer import percent

WINDOW = timedelta(hours=48)
NEARBY = timedelta(hours=6)  # a live session this close to the play is the same play
EVENT = "media.playback_finished"
PARTIAL = "media.playback_abandoned"  # #94: a play stopped before its end still counts its minutes
MIN_WATCHED = 60.0


class HistoryRewards:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        threshold: Callable[[str], float | None],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.threshold = threshold
        self.clock = clock

    def _finished(self, kind: str, share: float | None) -> bool:
        threshold = self.threshold(kind)
        return threshold is not None and share is not None and share >= threshold

    async def run(self) -> int:
        """Publish the recent plays of linked members the live watch missed: ``finished`` at the kind's
        threshold, else ``abandoned`` with the minutes watched."""
        now = utc_now(self.clock)
        published = 0
        async with self.database.unit_of_work() as uow:
            session = uow.session
            rows = (
                (
                    await session.execute(
                        select(Activity).where(
                            Activity.user_id.is_not(None),
                            Activity.counted.is_(True),
                            Activity.started_at >= now - WINDOW,
                            Activity.rewarded_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                share = row.progress if row.progress is not None else percent(row.watched_s, row.duration_s)
                finished = self._finished(row.kind, share)
                if not finished and (row.stopped_at is None or row.watched_s < MIN_WATCHED):
                    continue  # still playing, or too short to count
                row.rewarded_at = now  # looked at once: published now, or the live watch did
                if await self._seen_live(session, row, finished):
                    continue
                at = row.stopped_at or row.started_at
                event = EVENT if finished else PARTIAL
                result = await self.events.publish(
                    session,
                    event,
                    {
                        "object": str(row.object_id) if row.object_id else None,
                        "kind": row.kind,
                        "state_seq": 0,
                        "service": str(row.service_id),
                        "session": f"history:{row.ref}",  # told apart from a live session
                        "position_s": round(row.watched_s, 1),
                        "duration_s": row.duration_s,
                        "percent": share,
                        "occurred_at": at.isoformat(),
                        "watched_s": round(row.watched_s, 1),
                    },
                    occurred_at=at,
                    subject=SubjectRef("user", str(row.user_id)),
                    source="media",
                    dedup_key=f"{event}:history:{row.service_id}:{row.ref}",
                )
                if not result.duplicate:
                    published += 1
        if published:
            metrics.increment("media.playback.finished_from_history", published)
        return published

    async def _seen_live(self, session: AsyncSession, row: Activity, finished: bool) -> bool:
        """The live watch followed this play to its end (it published ``finished`` then, or, for a play
        stopped early, its ``abandoned``)."""
        start = row.started_at - NEARBY
        end = (row.stopped_at or row.started_at) + NEARBY
        lives = (
            await session.execute(
                select(PlaybackSession).where(
                    PlaybackSession.user_id == row.user_id,
                    PlaybackSession.ended.is_(True),
                    and_(PlaybackSession.updated_at >= start, PlaybackSession.started_at <= end),
                    PlaybackSession.object_id == row.object_id
                    if row.object_id
                    else PlaybackSession.title == row.title,
                )
            )
        ).scalars()
        return any(self._finished(live.kind, percent(live.max_position_s, live.duration_s)) for live in lives)
