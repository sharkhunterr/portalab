"""024 T004/T032/T037 — the capability conformance kits pass against the fake providers (what a real
connector subclasses); new media types, detail blocks, widgets, packs, palette actions and notification
categories register without touching the core and disappear with their owner; media events expose
normalized activity attributes for campaign/automation conditions."""

from datetime import UTC, datetime

import pytest

from portalab.capabilities.activity import CAPABILITY as ACTIVITY
from portalab.capabilities.media.testkit import (
    FakePlayback,
    FakeRequests,
    LibraryRecordKit,
    PlaybackContractKit,
    RequestServiceContractKit,
    library_record,
)
from portalab.capabilities.media_core import DetailBlock, register_media_type
from portalab.capabilities.statistics import StatisticDefinition
from tests.integration.media.conftest import MediaHarness

pytestmark = pytest.mark.integration


class TestFakeLibrary(LibraryRecordKit):
    async def records(self):  # type: ignore[no-untyped-def]
        return [
            library_record("1", title="Dune", ids={"tmdb": "438631"}, year=2021),
            library_record("2", kind="book", title="Dune", ids={"isbn": "9780441013593"}, pages=412),
        ]


class TestFakePlayback(PlaybackContractKit):
    async def make_provider(self):  # type: ignore[no-untyped-def]
        return FakePlayback()

    async def start_session(self, provider) -> None:  # type: ignore[no-untyped-def]
        provider.play("k", external_user_id="u", kind="movie", position_s=3, duration_s=10)


class TestFakeRequests(RequestServiceContractKit):
    async def make_provider(self):  # type: ignore[no-untyped-def]
        return FakeRequests()


def pack_definitions() -> list[dict]:
    import json
    from pathlib import Path

    packs = Path(__file__).resolve().parents[3] / "definitions" / "packs"
    out: list[dict] = []
    for name in ("media", "playback", "reading", "gaming"):
        out.extend(json.loads((packs / f"{name}.json").read_text())["definitions"])
    return out


async def test_extensibility(media: MediaHarness) -> None:
    owner = "plugin:radio"
    register_media_type(
        "radio.show", "radio:kind.show", owner=owner, finished_threshold=0.5, registry=media.types
    )
    with pytest.raises(ValueError):
        register_media_type("stolen", "x", owner=owner, registry=media.types)  # plugin kinds are namespaced

    async def block(object_id, viewer):  # type: ignore[no-untyped-def]
        return {}

    media.blocks.register(
        DetailBlock("radio.listeners", owner, "radio:listeners", "facts", block, kinds=("radio.show",))
    )
    result = await media.module.library.upsert(
        [library_record("r1", kind="radio.show", title="Night Show")], media.service(3)
    )
    assert result.added == 1 and media.module.threshold("radio.show") == 0.5
    assert [b.key for b in media.blocks.for_kind("radio.show")] == ["radio.listeners"]
    assert media.blocks.for_kind("movie") == []
    assert media.types.unregister(owner) == 1 and media.blocks.unregister(owner) == 1
    # first-party contributions are in place
    for key in ("media.continue", "media.recent", "media.now_playing", "media.requests"):
        assert media.widgets.get(key) is not None
    assert media.search.provider("media") is not None
    assert {a.id for a in media.search.actions()} >= {"media.open", "media.request"}
    assert {c.key for c in media.categories.all()} >= {"media.available", "media.request_updated"}
    for definition in pack_definitions():
        StatisticDefinition.model_validate(definition)
        for event in definition["event_types"]:
            assert media.ev.types.get(event) is not None


async def test_activity_attributes(media: MediaHarness) -> None:
    await media.module.library.upsert(
        [
            library_record(
                "a",
                title="Amélie",
                original_title="Le Fabuleux Destin",
                ids={"tmdb": "194"},
                genres=["Comedy", "romance"],
            )
        ],
        media.service(1),
    )
    provider = next(
        p.provider
        for p in media.ev.full.identity.capabilities.system_providers(ACTIVITY)
        if p.instance_ref == "media"
    )
    object_id = (await media.events("media.added"))[0][1]["object"]
    attributes = await provider.attributes("media.playback_finished", {"object": object_id})
    assert provider.handles("media.playback_finished") and not provider.handles("user.signed_in")
    assert attributes.media_kind == "movie" and attributes.genres == ("comedy", "romance")
    assert attributes.original_title == "Le Fabuleux Destin"
    assert await provider.attributes("media.playback_finished", {"object": "nope"}) is None
    assert datetime.now(UTC)
