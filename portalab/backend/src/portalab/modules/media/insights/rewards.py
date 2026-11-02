"""#94 — a play the live watch missed still counts: when a service's history (Plex, Tautulli, Grimmory…)
records a member's play, ``media.playback_finished`` (its end reached: the end credits when the media
server marks them, else the kind's threshold — #101) or ``media.playback_abandoned`` (stopped before, with
the minutes watched) is published for it — the events the progression rules, quests and the play streak
listen to — unless the live watch followed that play to its end: its verdict stands then, finished or not
(#101: a history rounds its percentages — 89.5 % read as 90 — and its minutes were the live watch's too).
Only the plays the portal lived: #341 — those after the member linked that account (``WINDOW`` of grace
before, #102), however late the catch-up, at most ``MAX_AGE`` back; without a link, the last ``WINDOW``.
An old history imported later never turns into XP."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import Activity, PlaybackSession, UserLink
from portalab.modules.media.observability import metrics
from portalab.modules.media.playback.normalizer import percent, reached_end
from portalab.modules.media.playback.poller import HISTORY

WINDOW = timedelta(hours=48)  # a play's grace before its account was linked — without a link, its age
MAX_AGE = timedelta(days=30)  # #341: a catch-up never reaches further back
NEARBY = timedelta(hours=6)  # a live session this close to the play is the same play
ALONGSIDE = timedelta(minutes=10)  # #101: a live session followed to its stop during the play is that play
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
        credits: Callable[[UUID], Awaitable[float | None]] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.threshold = threshold
        self.credits = credits
        self.clock = clock

    async def _credits(self, object_id: UUID | None) -> float | None:
        if self.credits is None or object_id is None:
            return None
        try:
            return await self.credits(object_id)
        except Exception:
            return None

    def _finished(
        self, kind: str, share: float | None, duration: float | None, credits: float | None
    ) -> bool:
        if share is None:
            return False
        if not duration:  # a share alone: the kind's threshold decides
            return reached_end(share, 1.0, self.threshold(kind))
        return reached_end(share * duration, duration, self.threshold(kind), credits)

    async def run(self) -> int:
        """Publish the recent plays of linked members the live watch missed: ``finished`` once their end
        is reached, else ``abandoned`` with the minutes watched."""
        now = utc_now(self.clock)
        published = 0
        # #341: when that account was linked to the member (none: the play's age decides)
        linked = (
            select(func.min(UserLink.created_at))
            .where(
                UserLink.service_id == Activity.service_id,
                UserLink.external_user_id == Activity.external_user_id,
                UserLink.user_id == Activity.user_id,
            )
            .correlate(Activity)
            .scalar_subquery()
        )
        async with self.database.unit_of_work() as uow:
            session = uow.session
            rows = (
                (
                    await session.execute(
                        select(Activity).where(
                            Activity.user_id.is_not(None),
                            Activity.counted.is_(True),
                            Activity.started_at >= now - MAX_AGE,
                            Activity.started_at >= func.coalesce(linked, now) - WINDOW,
                            Activity.rewarded_at.is_(None),
                            # #190: a game played is no film watched — its minutes are no watching time
                            Activity.kind != "game",
                        )
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                share = row.progress if row.progress is not None else percent(row.watched_s, row.duration_s)
                credits = await self._credits(row.object_id) if row.duration_s else None
                finished = self._finished(row.kind, share, row.duration_s, credits)
                if not finished and (row.stopped_at is None or row.watched_s < MIN_WATCHED):
                    continue  # still playing, or too short to count
                row.rewarded_at = now  # looked at once: published now, or the live watch did
                if await self._seen_live(session, row, credits):
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

    async def _seen_live(self, session: AsyncSession, row: Activity, credits: float | None) -> bool:
        """The live watch followed this play: it finished it within ``NEARBY``, or it followed it to its
        stop (its session ran alongside and ended normally) — it published that play's event already.
        Only a session that ended once its account was linked published anything (#102: a link attributes
        the account's past sessions to the member afterwards, silently — their plays count from history).
        #340: a play another history recorded (Plex's own, without its minutes) was not followed: only its
        end reached stands for it."""
        start = row.started_at - NEARBY
        end = (row.stopped_at or row.started_at) + NEARBY
        began, stopped = row.started_at - ALONGSIDE, (row.stopped_at or row.started_at) + ALONGSIDE
        lives = (
            await session.execute(
                select(PlaybackSession)
                .join(
                    UserLink,
                    and_(
                        UserLink.service_id == PlaybackSession.service_id,
                        UserLink.user_id == PlaybackSession.user_id,
                    ),
                )
                .where(
                    PlaybackSession.user_id == row.user_id,
                    PlaybackSession.ended.is_(True),
                    UserLink.created_at <= PlaybackSession.updated_at,
                    and_(PlaybackSession.updated_at >= start, PlaybackSession.started_at <= end),
                    PlaybackSession.object_id == row.object_id
                    if row.object_id
                    else PlaybackSession.title == row.title,
                )
            )
        ).scalars()
        return any(
            reached_end(live.max_position_s, live.duration_s, self.threshold(live.kind), credits)
            or (
                live.state == "stopped"
                and HISTORY not in live.session_key
                and live.started_at <= stopped
                and live.updated_at >= began
            )
            for live in lives
        )
