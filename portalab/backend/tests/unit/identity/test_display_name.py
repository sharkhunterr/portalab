# ruff: noqa: RUF001 — homoglyphs and full-width letters are the point of these tests
"""002 T008 — display-name key (NFKC + casefold), homoglyph/case collisions, validation limits."""

import pytest

from portalab.modules.identity.domain.display_name import (
    InvalidDisplayName,
    InvalidLogin,
    clean_display_name,
    display_name_key,
    login_lookup_key,
    normalize_login,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "variant",
    ["Alice", "ALICE", "alice", "  alice  ", "Ａｌｉｃｅ", "ａｌｉｃｅ"],  # full-width letters
)
def test_case_and_compatibility_variants_collide(variant: str) -> None:
    assert display_name_key(variant) == display_name_key("alice")


def test_ligatures_and_sharp_s_collide() -> None:
    assert display_name_key("ﬁnn") == display_name_key("Finn")  # U+FB01 ligature
    assert display_name_key("Strasse") == display_name_key("STRAẞE")
    assert display_name_key("straße") == display_name_key("STRASSE")


def test_inner_whitespace_is_collapsed() -> None:
    assert clean_display_name("Jean   Luc") == "Jean Luc"
    assert display_name_key("jean\tluc") == display_name_key("Jean Luc")


def test_accents_are_kept_distinct() -> None:
    assert display_name_key("Élodie") != display_name_key("Elodie")
    assert clean_display_name("Élodie") == "Élodie"


def test_mixed_scripts_are_refused() -> None:
    with pytest.raises(InvalidDisplayName) as caught:
        clean_display_name("Аlice")  # first letter is Cyrillic
    assert caught.value.extensions["reason"] == "mixed_scripts"
    assert clean_display_name("Алиса") == "Алиса"  # a single non-Latin script is fine


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("a", "length"),
        ("x" * 33, "length"),
        ("   ", "length"),
        ("bad<script>", "characters"),
        ("zero​width", "characters"),
        ("ctrl\x07char", "characters"),
        ("--", "empty"),
    ],
)
def test_invalid_display_names(raw: str, reason: str) -> None:
    with pytest.raises(InvalidDisplayName) as caught:
        clean_display_name(raw)
    assert caught.value.code == "user.display_name_invalid"
    assert caught.value.extensions["reason"] == reason


def test_limits_are_inclusive() -> None:
    assert clean_display_name("ab") == "ab"
    assert clean_display_name("y" * 32) == "y" * 32


def test_login_normalization() -> None:
    assert normalize_login("  Alice.Doe ") == "alice.doe"
    assert normalize_login("ＢＯＢ") == "bob"
    for bad in ("ab", "a b c", "-start", "émile", "x" * 65, "semi;colon"):
        with pytest.raises(InvalidLogin):
            normalize_login(bad)
    assert login_lookup_key("no spaces allowed") is None
    assert login_lookup_key("Carol") == "carol"
