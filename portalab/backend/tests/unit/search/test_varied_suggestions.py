"""#67 — header suggestions: media taken in turn from each type, so one type never fills every place."""

from types import SimpleNamespace

from portalab.modules.search.module import _varied


def _item(kind: str, title: str, type_: str = "") -> SimpleNamespace:
    return SimpleNamespace(kind=kind, title=title, facets={"type": type_} if type_ else {})


def test_media_suggestions_mix_the_types() -> None:
    items = [_item("media", f"game {n}", "game") for n in range(4)] + [
        _item("media", f"film {n}", "movie") for n in range(6)
    ]
    assert [i.title for i in _varied(items)] == ["game 0", "film 0", "game 1", "film 1", "game 2", "film 2"]


def test_other_sources_keep_their_first_four() -> None:
    items = [_item("wiki", f"page {n}") for n in range(9)]
    assert [i.title for i in _varied(items)] == ["page 0", "page 1", "page 2", "page 3"]
    assert _varied([]) == []
