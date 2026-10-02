"""008 T011 — snippets are plain-text segments (no markup), highlight accent-insensitively, window around
the first hit; cursors are opaque and tolerant; DDL helper rejects non-identifiers."""

import pytest

from portalab.capabilities.search.fts import decode_cursor, encode_cursor, fts_config, snippet, tsvector_ddl


def test_snippet_segments() -> None:
    segments = snippet("<b>Café</b> de Flore", ["cafe"])
    assert [(s.text, s.hit) for s in segments] == [("<b>", False), ("Café", True), ("</b> de Flore", False)]
    long = snippet("x " * 200 + "needle here", ["needle"], width=40)
    assert long[0].text == "…" and any(s.hit and s.text == "needle" for s in long)
    assert snippet("", ["a"]) == ()


def test_cursor_roundtrip_and_tolerance() -> None:
    assert decode_cursor(encode_cursor(20)) == 20
    assert decode_cursor("garbage!!") == 0 and decode_cursor(None) == 0
    assert decode_cursor(encode_cursor(10**9)) == 10_000


def test_configs_and_ddl() -> None:
    assert fts_config("fr-CA") == "french" and fts_config(None) == "simple"
    assert "GENERATED ALWAYS" in tsvector_ddl("wiki", "pages", ["title", "body"], config="english")[0]
    with pytest.raises(ValueError):
        tsvector_ddl("wiki", "pages; drop", ["title"])
