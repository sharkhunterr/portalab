"""Media events (T024; 007 envelope, ids and counters only — never titles, URLs or source payloads).

Catalog: ``media.added|updated|removed|availability_changed|merged|split``. Playback (subject = the linked
user, private): ``media.playback_started|progressed|paused|finished|abandoned|error`` deduplicated by
``(session, state_seq)`` (``finished`` once per session; ``via`` the portal's own player or reader, #103),
``media.resume_available``, ``media.cast_started`` (#103: sent to a casting device). Requests:
``media.request_created|updated|available`` deduplicated by ``(request, state)``. The radio (issue 227):
``media.radio_listened`` (slices of listening, counted by the server), ``media.radio_requested``; issue 228:
``media.leaving_watched`` (a title about to be deleted, watched to the end)."""

from typing import Literal

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:media"


class ObjectEvent(BaseModel):
    object: str
    kind: str


class AvailabilityChanged(ObjectEvent):
    available: bool


class Merged(BaseModel):
    object: str
    other: str


class Playback(BaseModel):
    object: str | None = None
    kind: str
    service: str
    session: str
    state_seq: int
    position_s: float
    duration_s: float | None = None
    percent: float | None = None
    occurred_at: str
    watched_s: float | None = None  # #94: the time actually watched, listened to or read in this sitting
    via: Literal["portal"] | None = None  # #103: played in the portal (its player, its reader)


class RadioListened(BaseModel):
    """Issue 227: a member listened to the radio in the portal's player — one per slice of ``minutes`` the
    stream was relayed to them (counted by the server, never told by the page)."""

    minutes: int
    session: str
    slice: int


class RadioRequested(BaseModel):
    """Issue 227: a member's song request taken by the radio's DJ."""

    request: str


class LeavingWatched(BaseModel):
    """Issue 228: a member played to the end a title about to be deleted (Maintainerr) — once per member and
    title: they rescued it."""

    object: str
    kind: str
    delete_at: str | None = None


class CastStarted(BaseModel):
    """#103: the portal's player sent a title to a casting device (Chromecast, AirPlay)."""

    object: str
    kind: str
    session: str


class ResumeAvailable(BaseModel):
    object: str
    kind: str
    percent: float


class RequestEvent(BaseModel):
    request: str
    object: str | None = None
    kind: str
    state: Literal["pending", "approved", "declined", "processing", "available", "failed", "cancelled"]


class RequestWatched(BaseModel):
    """A title a member asked for was watched by someone else (once per request and viewer): its asker's
    share of the joy — a little XP and Coins if the economy rewards it."""

    request: str
    object: str
    kind: str
    viewer: str  # who watched — for the administration's journal; members are never shown it


CATALOG_TYPES: dict[str, type[BaseModel]] = {
    "media.added": ObjectEvent,
    "media.updated": ObjectEvent,
    "media.removed": ObjectEvent,
    "media.availability_changed": AvailabilityChanged,
    "media.merged": Merged,
    "media.split": Merged,
}
PLAYBACK_TYPES = (
    "media.playback_started",
    "media.playback_progressed",
    "media.playback_paused",
    "media.playback_finished",
    "media.playback_abandoned",
    "media.playback_error",
)
REQUEST_TYPES = ("media.request_created", "media.request_updated", "media.request_available")


def register_event_types(registry: EventTypeRegistry) -> None:
    def add(event_type: EventType) -> None:
        if registry.get(event_type.name) is None:
            registry.register(event_type)

    for name, schema in CATALOG_TYPES.items():
        add(
            EventType(
                name=name,
                owner=OWNER,
                schema=schema,
                open_payload=False,
                retention_class="technical",
                visibility_class="public",
                aggregatable=frozenset({"kind"}) if "kind" in schema.model_fields else frozenset(),
                automatable=name in ("media.added", "media.availability_changed"),
            )
        )
    for name in PLAYBACK_TYPES:
        add(
            EventType(
                name=name,
                owner=OWNER,
                schema=Playback,
                open_payload=False,
                dedup_fields=("session", "state_seq"),
                retention_class="business",
                visibility_class="private",
                # #94: a sitting's minutes count whether it finished or not; finishing earns a bonus
                rewardable=frozenset({"kind", "percent", "duration_s", "position_s", "watched_s", "via"})
                if name in ("media.playback_finished", "media.playback_abandoned")
                else frozenset(),
                aggregatable=frozenset({"kind", "percent", "via"}),
                automatable=name in ("media.playback_started", "media.playback_finished"),
            )
        )
    add(
        EventType(
            name="media.cast_started",
            owner=OWNER,
            schema=CastStarted,
            open_payload=False,
            dedup_fields=("session",),
            retention_class="business",
            visibility_class="private",
            rewardable=frozenset({"kind"}),
            aggregatable=frozenset({"kind"}),
        )
    )
    # issue 227: the radio listened to and a song asked for; issue 228: a title rescued by watching it
    for name, schema, dedup, fields in (
        ("media.radio_listened", RadioListened, ("session", "slice"), frozenset({"minutes"})),
        ("media.radio_requested", RadioRequested, ("request",), frozenset()),
        ("media.leaving_watched", LeavingWatched, ("object",), frozenset({"kind"})),
    ):
        add(
            EventType(
                name=name,
                owner=OWNER,
                schema=schema,
                open_payload=False,
                dedup_fields=dedup,
                retention_class="business",
                visibility_class="private",
                rewardable=fields | (frozenset({"kind"}) if "kind" in schema.model_fields else frozenset()),
                aggregatable=frozenset({"kind"}) if "kind" in schema.model_fields else frozenset(),
                automatable=True,
            )
        )
    add(
        EventType(
            name="media.resume_available",
            owner=OWNER,
            schema=ResumeAvailable,
            open_payload=False,
            retention_class="technical",
            visibility_class="private",
        )
    )
    add(
        EventType(
            name="media.request_watched",
            owner=OWNER,
            schema=RequestWatched,
            open_payload=False,
            dedup_fields=("request",),
            retention_class="business",
            visibility_class="private",
            rewardable=frozenset({"kind"}),
            aggregatable=frozenset({"kind"}),
            automatable=True,
        )
    )
    for name in REQUEST_TYPES:
        add(
            EventType(
                name=name,
                owner=OWNER,
                schema=RequestEvent,
                open_payload=False,
                dedup_fields=("request", "state"),
                retention_class="business",
                visibility_class="private",
                aggregatable=frozenset({"kind", "state"}),
                automatable=True,
            )
        )
