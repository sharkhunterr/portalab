"""A title someone asked for, watched by another member: ``media.request_watched`` for the asker — once per
request and viewer (a whole series watched counts once), never for their own plays, only for a request
that brought the title in (``available``). Its subject is who asked; who watched is in it for the
administration's journal only (members never see it)."""

from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.modules.media.models import MediaObject, MediaRequest

CONSUMER = "media.request_watched"
OWNER = "module:media"


class RequestWatched:
    def __init__(self, database: Database, events: EventPublisher) -> None:
        self.database = database
        self.events = events

    def consumer(self) -> Consumer:
        return Consumer(
            CONSUMER, frozenset({"media.playback_finished"}), self.handle, OWNER, replay_safe=True
        )

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        raw = envelope.payload.get("object")
        if ctx.replay or envelope.subject_type != "user" or not envelope.subject_id or not raw:
            return  # a replay never rewards again
        viewer = UUID(envelope.subject_id)
        async with self.database.unit_of_work() as uow:
            lineage: list[UUID] = []
            current = await uow.session.get(MediaObject, UUID(str(raw)))
            while current is not None and len(lineage) < 4:  # an episode, its season, its series
                lineage.append(current.id)
                current = await uow.session.get(MediaObject, current.parent_id) if current.parent_id else None
            if not lineage:
                return
            asked = (
                await uow.session.execute(
                    select(MediaRequest).where(
                        MediaRequest.object_id.in_(lineage),
                        MediaRequest.state == "available",
                        MediaRequest.requester_user_id.is_not(None),
                        MediaRequest.requester_user_id != viewer,
                    )
                )
            ).scalars()
            for request in asked:
                await self.events.publish(
                    uow.session,
                    "media.request_watched",
                    {
                        "request": str(request.id),
                        "object": str(request.object_id),
                        "kind": str(request.external_ref.get("kind", "")),
                        "viewer": str(viewer),
                    },
                    occurred_at=envelope.occurred_at,
                    subject=SubjectRef("user", str(request.requester_user_id)),
                    source="media",
                    dedup_key=f"media.request_watched:{request.id}:{viewer}",
                )
