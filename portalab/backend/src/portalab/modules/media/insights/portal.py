"""#282 — what a member reads or listens to in the portal counts in the statistics.

The statistics read ``media.activity``, the services' own histories. A sitting in the portal's reader or
player is in none of them: Grimmory records the sessions of its own reader only (the progress the portal
writes back creates none). This consumer turns each ended portal sitting (``media.playback_finished`` /
``media.playback_abandoned``) into an activity row of the member's: the time spent, how far they got, the
work. The row is marked rewarded at once — the sitting's own events gave its XP (:mod:`.rewards` never
publishes it again). A new consumer reads the retained events from the start: past sittings count too."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.capabilities.media import ACTIVITY_KINDS
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.insights.ingest import _Resolver, mark_days
from portalab.modules.media.models import Activity, MediaObject

CONSUMER = "media.portal_activity"
OWNER = "module:media"
TYPES = frozenset({"media.playback_finished", "media.playback_abandoned"})
BOOK_KINDS = ("book", "audiobook")
PLATFORM = "Portalab"


def portal_sitting(payload: Mapping[str, Any]) -> bool:
    """A sitting in the portal's reader or player — not a play a service's history told (``history:``)."""
    if str(payload.get("session") or "").startswith("history:"):
        return False
    # the first sittings (before ``via``) were the reader's and the player's: books and audiobooks only
    return payload.get("via") == "portal" or payload.get("kind") in BOOK_KINDS


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class PortalActivity:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    def consumer(self) -> Consumer:
        return Consumer(CONSUMER, TYPES, self.handle, OWNER, replay_safe=True)

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        payload = envelope.payload
        kind = str(payload.get("kind") or "")
        if (
            envelope.type not in TYPES
            or envelope.subject_type != "user"
            or not envelope.subject_id
            or not payload.get("object")
            or not payload.get("service")
            or kind not in ACTIVITY_KINDS
            or not portal_sitting(payload)
        ):
            return
        watched = _number(payload.get("watched_s"))
        if watched is None and kind == "book":  # a book reports the time spent reading as its position
            watched = _number(payload.get("position_s"))
        if not watched or watched <= 0:
            return  # nothing measured: no time to count
        await self.store(
            ref=f"portal:{envelope.event_id}",
            user=UUID(envelope.subject_id),
            service=UUID(str(payload["service"])),
            object_id=UUID(str(payload["object"])),
            kind=kind,
            watched=watched,
            duration=_number(payload.get("duration_s")),
            share=_number(payload.get("percent")),
            ended=envelope.occurred_at,
        )

    async def store(
        self,
        *,
        ref: str,
        user: UUID,
        service: UUID,
        object_id: UUID,
        kind: str,
        watched: float,
        duration: float | None,
        share: float | None,
        ended: datetime,
    ) -> bool:
        """One sitting as an activity row of the member's; False when it is there already (a replay)."""
        started = ended - timedelta(seconds=watched)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            found, work = await _Resolver(session).of(object_id)
            obj = await session.get(MediaObject, found) if found is not None else None
            if obj is None:
                return False  # no longer in the catalog
            inserted = await session.execute(
                insert(Activity)
                .values(
                    service_id=service,
                    ref=ref[:200],
                    family=None,
                    priority=10,
                    counted=True,
                    external_user_id=f"portal:{user}",  # no service account: account links never move it
                    user_id=user,
                    kind=kind,
                    title=obj.title[:500] or "?",
                    object_id=obj.id,
                    work_id=work or obj.id,
                    ids={},
                    year=obj.year,
                    started_at=started,
                    stopped_at=ended,
                    watched_s=watched,
                    duration_s=duration,
                    progress=min(1.0, max(0.0, share)) if share is not None else None,
                    platform=PLATFORM,
                    received_at=now,
                    rewarded_at=now,  # its own events gave its XP
                )
                .on_conflict_do_nothing(constraint="uq_activity_service_ref")
                .returning(Activity.id)
            )
            if inserted.scalar_one_or_none() is None:
                return False
            await mark_days(session, [started])
        return True
