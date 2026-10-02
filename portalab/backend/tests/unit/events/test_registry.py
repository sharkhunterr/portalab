"""007 T005/T032/T033 — registry: schemas, personal fields refused, versions, duplicates, annotations
(rewardable, aggregatable, automatable), owner-tagged unregister; payload validation outcomes."""

import pytest
from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeError, EventTypeRegistry
from portalab.modules.events.registry.types import validate

pytestmark = pytest.mark.unit


class Played(BaseModel):
    media_ref: str
    seconds: int
    service_id: str


def _registry() -> EventTypeRegistry:
    registry = EventTypeRegistry()
    registry.register(
        EventType(
            "media.played",
            "module:media",
            schema=Played,
            open_payload=False,
            dedup_fields=("media_ref",),
            rewardable=frozenset({"seconds"}),
            aggregatable=frozenset({"seconds", "service_id"}),
            automatable=True,
        )
    )
    return registry


def test_registration_rules() -> None:
    registry = _registry()
    assert registry.get("media.played").automatable  # type: ignore[union-attr]
    with pytest.raises(EventTypeError):
        registry.register(EventType("media.played", "module:other"))  # differs ⇒ duplicate refused

    class WithEmail(BaseModel):
        email: str

    with pytest.raises(EventTypeError, match="personal"):
        registry.register(EventType("user.mailed", "m", schema=WithEmail))
    with pytest.raises(EventTypeError, match="undeclared"):
        registry.register(EventType("media.x", "m", schema=Played, rewardable=frozenset({"nope"})))
    with pytest.raises(EventTypeError):
        registry.register(EventType("Bad Name", "m"))
    with pytest.raises(EventTypeError):
        registry.register(EventType("media.v0", "m", version=0))


def test_owner_unregister() -> None:
    registry = _registry()
    registry.register(EventType("plugin_w.done", "plugin:w"))
    assert registry.unregister("plugin:w") == 1
    assert [t.name for t in registry.all()] == ["media.played"]


@pytest.mark.parametrize(
    ("name", "version", "payload", "reason"),
    [
        ("nope.nope", 1, {}, "unknown_type"),
        ("media.played", 2, {"media_ref": "m", "seconds": 1, "service_id": "s"}, "version_unsupported"),
        ("media.played", 1, {"media_ref": "m"}, "invalid_payload"),
        (
            "media.played",
            1,
            {"media_ref": "m", "seconds": 1, "service_id": "s", "extra": 1},
            "invalid_payload",
        ),
        (
            "media.played",
            1,
            {"media_ref": "m", "seconds": 1, "service_id": "s", "api_token": "x"},
            "invalid_payload",
        ),
    ],
)
def test_validation_outcomes(name: str, version: int, payload: dict, reason: str) -> None:  # type: ignore[type-arg]
    assert validate(_registry(), name, version, payload).reason == reason


def test_personal_fields_in_open_payloads() -> None:
    registry = EventTypeRegistry()
    registry.register(EventType("note.added", "m"))
    assert validate(registry, "note.added", 1, {"display_name": "Alice"}).reason == "pii_detected"
    assert validate(registry, "note.added", 1, {"nested": {"email": "a@b.c"}}).reason == "pii_detected"
    ok = validate(registry, "note.added", 1, {"note_ref": "n1"})
    assert ok.reason is None and ok.payload == {"note_ref": "n1"}
