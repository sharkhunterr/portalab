"""``InvalidationBridge`` (T034; R8): domain events listed in a widget's ``refresh.events`` become live
``widget.invalidate`` messages on the 004 stream, carrying **the widget key only** and restricted to holders
of the widget's permission; the client refetch re-authorizes. Duplicates are harmless (idempotent)."""

from collections.abc import Callable

from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.core.db import Database
from portalab.core.live import publish_live
from portalab.core.time import Clock

CONSUMER = "dashboard.widget_invalidation"
OWNER = "module:dashboard"
TOPIC = "widget.invalidate"


def watched_types(registry: WidgetRegistry) -> frozenset[str]:
    return frozenset(event for w in registry.widgets() for event in w.definition.refresh.events)


def invalidation_consumer(
    database: Database, registry: WidgetRegistry, types: frozenset[str], *, clock: Clock | None = None
) -> Consumer:
    async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
        if ctx.replay:
            return  # replays never push live invalidations
        keys = [
            (w.definition.key, w.definition.required_permission)
            for w in registry.widgets()
            if envelope.type in w.definition.refresh.events
        ]
        if not keys:
            return
        async with database.unit_of_work() as uow:
            for key, permission in keys:
                await publish_live(
                    uow.session, topic=TOPIC, payload={"widget": key}, permission=permission, clock=clock
                )

    return Consumer(CONSUMER, types, handle, OWNER, replay_safe=True)


InvalidationFactory = Callable[[], Consumer]
