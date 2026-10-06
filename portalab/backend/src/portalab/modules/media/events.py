"""Media events (T024; 007 envelope, ids and counters only — never titles, URLs or source payloads).

Catalog: ``media.added|updated|removed|availability_changed|merged|split``. Playback (subject = the linked
user, private): ``media.playback_started|progressed|paused|finished|abandoned|error`` deduplicated by
``(session, state_seq)`` (``finished`` once per session), ``media.resume_available``. Requests:
``media.request_created|updated|available`` deduplicated by ``(request, state)``."""

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


class ResumeAvailable(BaseModel):
    object: str
    kind: str
    percent: float


class RequestEvent(BaseModel):
    request: str
    object: str | None = None
    kind: str
    state: Literal["pending", "approved", "declined", "processing", "available", "failed", "cancelled"]


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
                rewardable=frozenset({"kind", "percent", "duration_s", "position_s"})
                if name == "media.playback_finished"
                else frozenset(),
                aggregatable=frozenset({"kind", "percent"}),
                automatable=name in ("media.playback_started", "media.playback_finished"),
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
