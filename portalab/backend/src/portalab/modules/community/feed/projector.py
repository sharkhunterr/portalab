"""Feed projector (T010; US2, R5): a 007 consumer turning allow-listed domain events into feed entries.

* only types listed in ``community.feed.eventTypes`` whose 007 visibility class is ``public`` or
  ``community`` — a private or restricted event never becomes a feed entry, whatever the setting says;
* the actor must currently allow ``community_activity`` for members (Private actors never enter);
* idempotent on ``source_event_id`` (a redelivery or replay projects nothing new);
* entries keep ids and scalar parameters only; the text is localized at render time
  (``community:feed.<type>``) and links back to the source event.
There is deliberately no like, reaction or comment on an entry."""

from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope, EventTypeRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import VisibilityFilter
from portalab.modules.community.models import FeedEntry
from portalab.modules.community.observability import metrics
from portalab.modules.community.preferences import ACTIVITY
from portalab.modules.community.settings import CommunityConfig

CONSUMER = "community.feed"
OWNER = "module:community"
SHAREABLE = ("public", "community")
MAX_PARAMS = 8


def actor_of(envelope: Envelope) -> UUID | None:
    if envelope.actor_user_id is not None:
        return envelope.actor_user_id
    if envelope.subject_type == "user" and envelope.subject_id:
        try:
            return UUID(envelope.subject_id)
        except ValueError:
            return None
    return None


def scalar_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, bool | int | float) or (isinstance(value, str) and len(value) <= 120):
            out[key] = value
        if len(out) == MAX_PARAMS:
            break
    return out


class FeedProjector:
    def __init__(
        self,
        database: Database,
        event_types: EventTypeRegistry,
        visibility: VisibilityFilter,
        config: Callable[[], CommunityConfig],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.event_types = event_types
        self.visibility = visibility
        self.config = config
        self.clock = clock

    def consumer(self) -> Consumer:
        return Consumer(CONSUMER, frozenset({"*"}), self.handle, OWNER, replay_safe=True)

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        await self.project(envelope)

    async def project(self, envelope: Envelope) -> bool:
        if envelope.type not in self.config().feed_event_types:
            return False
        event_type = self.event_types.get(envelope.type)
        if event_type is None or event_type.visibility_class not in SHAREABLE:
            return False
        actor = actor_of(envelope)
        if actor is None:
            return False
        if await self.visibility.effective_level(actor, ACTIVITY, None) not in SHAREABLE:
            metrics.increment("community.feed.skipped_private")
            return False
        subject = f"{envelope.subject_type}:{envelope.subject_id}" if envelope.subject_type else None
        async with self.database.unit_of_work() as uow:
            inserted = await uow.session.scalar(
                insert(FeedEntry)
                .values(
                    source_event_id=envelope.event_id,
                    actor_user_id=actor,
                    kind=envelope.type,
                    subject_ref=subject[:200] if subject else None,
                    text_key=f"community:feed.{envelope.type}",
                    params=scalar_params(envelope.payload),
                    visibility_class=event_type.visibility_class,
                    occurred_at=envelope.occurred_at,
                    created_at=utc_now(self.clock),
                )
                .on_conflict_do_nothing(index_elements=[FeedEntry.source_event_id])
                .returning(FeedEntry.id)
            )
        if inserted is not None:
            metrics.increment("community.feed.projected")
        return inserted is not None
