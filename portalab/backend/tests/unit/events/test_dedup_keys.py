"""007 T008 — dedup keys: reliable source id wins; otherwise a deterministic composite of declared fields;
events differing only by timestamp are not collapsed; never a timestamp alone."""

import pytest

from portalab.capabilities.events import EventType
from portalab.modules.events.dedup.keys import DedupKeyError, derive

pytestmark = pytest.mark.unit

SOURCED = EventType("media.added", "m", source_id_reliable=True, dedup_fields=("item_ref",))
FIELDS = EventType("media.played", "m", dedup_fields=("item_ref", "session_ref"))
NONE = EventType("note.added", "m")


def test_source_id_wins() -> None:
    a = derive(SOURCED, {"item_ref": "x"}, source="plex-a", source_event_id="42", explicit=None)
    b = derive(SOURCED, {"item_ref": "y"}, source="plex-a", source_event_id="42", explicit=None)
    assert a == b == "src:plex-a:42"
    assert derive(SOURCED, {"item_ref": "x"}, source="plex-b", source_event_id="42", explicit=None) != a


def test_declared_fields_composite_is_deterministic_and_ignores_timestamps() -> None:
    first = derive(
        FIELDS,
        {"item_ref": "m1", "session_ref": "s1", "at": "2026-10-01T10:00:00Z"},
        source="x",
        source_event_id=None,
        explicit=None,
    )
    later = derive(
        FIELDS,
        {"session_ref": "s1", "item_ref": "m1", "at": "2026-10-02T10:00:00Z"},
        source="x",
        source_event_id=None,
        explicit=None,
    )
    other = derive(
        FIELDS, {"item_ref": "m1", "session_ref": "s2"}, source="x", source_event_id=None, explicit=None
    )
    assert first == later and first != other and first.startswith("f:")  # type: ignore[union-attr]


def test_no_dedup_without_declaration() -> None:
    assert derive(NONE, {"at": "2026-10-01"}, source="x", source_event_id=None, explicit=None) is None


@pytest.mark.parametrize("explicit", ["2026-10-01T10:00:00Z", "1696154400", "  "])
def test_timestamp_only_keys_are_refused(explicit: str) -> None:
    with pytest.raises(DedupKeyError):
        derive(NONE, {}, source="x", source_event_id=None, explicit=explicit)
    with pytest.raises(DedupKeyError):
        derive(
            EventType("t.x", "m", dedup_fields=("at",)),
            {"at": "2026-10-01T10:00:00Z"},
            source="x",
            source_event_id=None,
            explicit=None,
        )


def test_missing_dedup_field() -> None:
    with pytest.raises(DedupKeyError):
        derive(FIELDS, {"item_ref": "m1"}, source="x", source_event_id=None, explicit=None)
