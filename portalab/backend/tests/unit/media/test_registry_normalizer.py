"""024 T038/T021 — owner-tagged media-type and detail-block registries (a plugin's contributions disappear
with it); baseline kinds and thresholds; normalizer decisions (state changes always, progress throttled,
finished only at/above the kind's threshold, explicit-only kinds never finish from a position)."""

from datetime import UTC, datetime, timedelta

import pytest

from portalab.capabilities.media import SourcePlayback
from portalab.capabilities.media_core import (
    DetailBlock,
    DetailBlockRegistry,
    MediaRegistryError,
    MediaTypeRegistry,
    register_baseline,
    register_media_type,
)
from portalab.modules.media.common import safe_ref, sort_title, strong_ids
from portalab.modules.media.playback.normalizer import on_end, on_update

T = datetime(2026, 1, 1, tzinfo=UTC)


async def _load(object_id, viewer):  # type: ignore[no-untyped-def]
    return {}


def test_registries_are_owner_tagged() -> None:
    types = MediaTypeRegistry()
    register_baseline(types)
    assert {t.kind for t in types.all()} >= {"movie", "episode", "book", "game", "track"}
    assert types.get("game").finished_threshold is None and types.get("book").finished_threshold == 0.95  # type: ignore[union-attr]
    register_media_type("radio.show", "x", owner="plugin:radio", registry=types)
    for bad in (
        lambda: register_media_type("movie", "x", owner="plugin:radio", registry=types),
        lambda: register_media_type("Bad Kind", "x", owner="module:x", registry=types),
        lambda: register_media_type("radio.x", "x", owner="module:x", finished_threshold=2, registry=types),
    ):
        with pytest.raises(MediaRegistryError):
            bad()
    blocks = DetailBlockRegistry()
    blocks.register(DetailBlock("radio.a", "plugin:radio", "t", "facts", _load))
    blocks.register(DetailBlock("core.b", "module:media", "t", "list", _load, order=1))
    assert [b.key for b in blocks.for_kind("movie")] == ["core.b", "radio.a"]
    assert types.unregister("plugin:radio") == 1 and blocks.unregister("plugin:radio") == 1
    assert types.get("radio.show") is None and [b.key for b in blocks.for_kind("movie")] == ["core.b"]


def report(state: str, position: float = 0) -> SourcePlayback:
    return SourcePlayback("k", state, "movie", "t", position_s=position)  # type: ignore[arg-type]


def test_normalizer() -> None:
    assert (
        on_update("playing", T, T + timedelta(seconds=5), report("paused"), 60).event
        == "media.playback_paused"
    )
    assert (
        on_update("paused", T, T + timedelta(seconds=5), report("playing"), 60).event
        == "media.playback_progressed"
    )
    assert on_update("playing", T, T + timedelta(seconds=5), report("playing"), 60).event is None
    assert (
        on_update("playing", T, T + timedelta(seconds=61), report("playing"), 60).event
        == "media.playback_progressed"
    )
    assert on_update("playing", T, T, report("stopped"), 60).state == "stopped"
    assert on_end(90, 100, 0.9) == "media.playback_finished"
    assert on_end(89, 100, 0.9) == "media.playback_abandoned"
    assert on_end(100, 100, None) == "media.playback_abandoned"  # games: explicit ending only
    assert on_end(50, None, 0.9) == "media.playback_abandoned"
    # #101: where the media server marks the end credits, they decide — not the threshold
    assert on_end(7790, 8700, 0.9, 8136) == "media.playback_abandoned"  # 89.5 %: six minutes before them
    assert on_end(8110, 8700, 0.9, 8136) == "media.playback_finished"  # stopped as they begin
    assert on_end(5500, 6000, 0.9, 5300) == "media.playback_finished"  # long credits: 91.7 % is the end
    assert on_end(100, 100, None, 80) == "media.playback_abandoned"  # explicit-only kinds still never
    assert on_end(95, 100, 0.9, 100) == "media.playback_finished"  # a marker at the very end is no clue


def test_helpers() -> None:
    assert sort_title("The Matrix") == "matrix" and sort_title("Le Fabuleux Destin") == "fabuleux destin"
    assert strong_ids({"TMDB": " 603 ", "bogus": "1", "imdb": "has space"}) == {"tmdb": "603"}
    assert safe_ref("https://user:pw@img.example:8443/p.jpg?token=x#f") == "https://img.example:8443/p.jpg"
    assert safe_ref("javascript:alert(1)") == "javascript:alert(1)" or safe_ref("ftp://x/y") is None
    assert safe_ref("poster/12?sig=abc") == "poster/12"
