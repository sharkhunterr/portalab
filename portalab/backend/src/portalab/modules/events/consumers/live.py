"""SSE subscriber (T029; R10): events whose type declares ``live_permission`` are relayed to the 001 stream
as live notifications, filtered there by permission — and, for private types, by audience (the subject user
only). Payloads are not relayed: subscribers refetch through the regular, authorized APIs."""

from uuid import UUID

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope, EventTypeRegistry
from portalab.core.db import Database
from portalab.core.live import publish_live

NAME = "events.live"


def live_consumer(database: Database, event_types: EventTypeRegistry) -> Consumer:
    async def relay(event: Envelope, ctx: ConsumerContext) -> None:
        registered = event_types.get(event.type)
        if registered is None or registered.live_permission is None or ctx.replay:
            return
        audience = None
        if registered.visibility_class == "private":
            if event.subject_type != "user" or not event.subject_id:
                return
            audience = UUID(event.subject_id)
        if not await ctx.idempotent_effect(f"live:{event.event_id}"):
            return
        async with database.unit_of_work() as uow:
            await publish_live(
                uow.session,
                topic=event.type,
                payload={
                    "event_id": str(event.event_id),
                    "subject_type": event.subject_type,
                    "subject_id": event.subject_id,
                },
                permission=registered.live_permission,
                audience_user_id=audience,
            )

    return Consumer(NAME, frozenset({"*"}), relay, "module:events", replay_safe=False)
