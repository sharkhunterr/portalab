"""A title someone asked for, watched by another member: ``media.request_watched`` for the asker — once per
request and viewer (a whole series watched counts once), never for their own plays, only for a request
that brought the title in (``available``). Its subject is who asked; who watched is in it for the
administration's journal only (members never see it).

Issue 228: a title about to be deleted (Maintainerr), played to the end — ``media.leaving_watched`` for the
member who played it, once per member and title (an episode rescues its series or season)."""

from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.modules.media.models import MediaObject, MediaRequest

CONSUMER = "media.request_watched"
LEAVING = "media.leaving_watched"
OWNER = "module:media"


async def lineage(session: Any, raw: str) -> list[UUID]:
    """The object played and what holds it: an episode, its season, its series."""
    out: list[UUID] = []
    current = await session.get(MediaObject, UUID(str(raw)))
    while current is not None and len(out) < 4:
        out.append(current.id)
        current = await session.get(MediaObject, current.parent_id) if current.parent_id else None
    return out


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
            held = await lineage(uow.session, str(raw))
            if not held:
                return
            asked = (
                await uow.session.execute(
                    select(MediaRequest).where(
                        MediaRequest.object_id.in_(held),
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


class LeavingWatched:
    """Issue 228: the rescue bounty — a play finished on a title Maintainerr is about to delete."""

    def __init__(self, database: Database, events: EventPublisher, cleanup: Any) -> None:
        self.database = database
        self.events = events
        self.cleanup = cleanup

    def consumer(self) -> Consumer:
        return Consumer(LEAVING, frozenset({"media.playback_finished"}), self.handle, OWNER, replay_safe=True)

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        raw = envelope.payload.get("object")
        if ctx.replay or envelope.subject_type != "user" or not envelope.subject_id or not raw:
            return  # a replay never rewards again
        if not self.cleanup.configured():
            return
        try:
            leaving = {entry.object_id: entry for entry in await self.cleanup.leaving()}
        except Exception:
            return  # Maintainerr does not answer: nothing to rescue now
        if not leaving:
            return
        async with self.database.unit_of_work() as uow:
            for object_id in await lineage(uow.session, str(raw)):
                entry = leaving.get(object_id)
                if entry is None:
                    continue
                delete_at = getattr(entry.item, "delete_at", None)
                await self.events.publish(
                    uow.session,
                    LEAVING,
                    {
                        "object": str(object_id),
                        "kind": str(getattr(entry.item, "kind", "") or envelope.payload.get("kind") or ""),
                        "delete_at": delete_at.isoformat() if delete_at else None,
                    },
                    occurred_at=envelope.occurred_at,
                    subject=SubjectRef("user", envelope.subject_id),
                    source="media",
                    dedup_key=f"{LEAVING}:{object_id}:{envelope.subject_id}",
                )
                return  # the closest one held: a series rescued once
