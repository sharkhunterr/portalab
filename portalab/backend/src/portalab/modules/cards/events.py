"""Issue 234: the cards' events, for the achievements and the reward rules the administrators set — a booster
opened (what it held: its cards, the rarest, its legendaries, its foils) and a collection completed (every
card of a work's set owned, once per member and set). Ids and counters only, never titles."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:cards"
PACK_OPENED = "cards.pack_opened"
SET_COMPLETED = "cards.set_completed"


class PackOpened(BaseModel):
    pack: str
    source: str  # content (a film, a season), shop, trial
    cards: int
    best: str  # the rarest card's rarity
    legendary: int
    foil: int


class SetCompleted(BaseModel):
    set: str
    object: str  # the work
    kind: str  # movie, series
    size: int


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, dedup, fields in (
        (PACK_OPENED, PackOpened, ("pack",), frozenset({"source", "cards", "best", "legendary", "foil"})),
        (SET_COMPLETED, SetCompleted, ("set",), frozenset({"kind", "size"})),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    dedup_fields=dedup,
                    retention_class="business",
                    visibility_class="private",
                    rewardable=fields,
                    aggregatable=fields,
                    automatable=True,
                )
            )
