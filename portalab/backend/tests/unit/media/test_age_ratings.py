"""Issue 478 — a title's age ratings in full: every release TMDB tells (cinema, TV, platforms), the
household's rule « home viewing first » (the TV's rating, else the platforms', else the cinema's), and the
CNC's list."""

from typing import Any

from portalab.connectors.tmdb import _releases
from portalab.modules.media.ratings.cnc import VISA_NOTE, fold, parse, titles_of, warning
from portalab.modules.media.restrictions import title_age, warnings_of

MAD_MAX: dict[str, Any] = {
    "certifications": {"FR": "TP", "US": "R"},
    "releases": [
        {"country": "FR", "type": "cinema", "certification": "TP", "note": "Visa CNC 142250"},
        {"country": "FR", "type": "digital", "certification": "16", "note": "Netflix"},
        {"country": "FR", "type": "digital", "certification": "18", "note": "Prime Video"},
        {"country": "FR", "type": "tv", "certification": "12", "note": "Novo19"},
        {"country": "US", "type": "cinema", "certification": "R"},
    ],
}


def test_the_tv_rating_comes_first() -> None:
    assert title_age(MAD_MAX, "fr/TP", "FR") == 12  # « tous publics » at the cinema, -12 on TV


def test_then_the_platforms_then_the_cinema() -> None:
    no_tv = {**MAD_MAX, "releases": [r for r in MAD_MAX["releases"] if r["type"] != "tv"]}
    assert title_age(no_tv, "fr/TP", "FR") == 18  # the strictest platform
    cinema = {"releases": [{"country": "FR", "type": "cinema", "certification": "TP"}]}
    assert title_age(cinema, "fr/12", "FR") == 12  # the media server's own rating among the cinema's


def test_details_looked_up_before_rate_as_they_did() -> None:
    assert title_age({"certifications": {"FR": "TP", "US": "R"}}, "fr/TP", "FR") == 0
    assert title_age({"certifications": {"US": "R"}}, None, "FR") == 17  # no French rating: the strictest


def test_tmdb_tells_every_release_of_the_main_countries() -> None:
    document = {
        "release_dates": {
            "results": [
                {
                    "iso_3166_1": "FR",
                    "release_dates": [
                        {
                            "type": 3,
                            "certification": "TP",
                            "note": "Visa CNC 142250",
                            "release_date": "2015-05-14",
                        },
                        {"type": 6, "certification": "12", "descriptors": ["violence"], "note": "Novo19"},
                        {"type": 4, "certification": ""},  # unrated: left out
                    ],
                },
                {"iso_3166_1": "JP", "release_dates": [{"type": 3, "certification": "PG12"}]},  # not followed
            ]
        }
    }
    found = _releases(document, "FR")
    assert [(r["country"], r["type"], r["certification"]) for r in found] == [
        ("FR", "cinema", "TP"),
        ("FR", "tv", "12"),
    ]
    assert found[0]["date"] == "2015-05-14" and found[1]["descriptors"] == ["violence"]


def test_the_cnc_list_is_read_as_published() -> None:
    raw = (
        "﻿Titre;Réalisation;Production;Format;Date;Nationalité;N° de visa;Décision;Localisation\n"
        "Mad Max : Fury road;George Miller;KM;Long-métrage;2015;Australie;142250;Avertissement;CNC\n"
        "À bout de nerfs;Pierre Seguin;Gem;Court-métrage;1988;France;67623;Tout public;AN\n"
        "Mad Max 2 : Le défi. Mad Max 2;G. Miller;KM;Long-métrage;1982;Australie;55672;Avertissement;X\n"
    ).encode()
    visas = parse(raw)
    assert [v["visa"] for v in visas] == [142250, 55672]  # feature films only
    assert visas[0] == {
        "visa": 142250,
        "title": "Mad Max : Fury road",
        "key": "madmaxfuryroad",
        "year": 2015,
        "direction": "George Miller",
        "decision": "Avertissement",
    }
    assert visas[1]["key"] == fold("Mad Max 2 : Le défi")
    assert titles_of("Mad Max 2 : Le défi. Mad Max 2") == ["Mad Max 2 : Le défi", "Mad Max 2"]
    assert warning("Avertissement") and not warning("Tout public")
    assert VISA_NOTE.search("Visa CNC 142250").group(1) == "142250"  # type: ignore[union-attr]


def test_the_administrator_orders_the_ratings() -> None:
    assert title_age(MAD_MAX, "fr/TP", "FR", "tv,home,cinema") == 12  # the default: home viewing first
    assert title_age(MAD_MAX, "fr/TP", "FR", "cinema,tv,home") == 0  # the cinema's « tous publics »
    assert title_age(MAD_MAX, "fr/TP", "FR", "home,tv,cinema") == 18  # the strictest platform
    assert title_age(MAD_MAX, "fr/TP", "FR", "strictest") == 18  # every rating at once
    assert title_age(MAD_MAX, "fr/TP", "FR", "tv,tv,cinema") == 12  # not an order: the default holds


RESIDENT_EVIL: dict[str, Any] = {
    "certifications": {"FR": "12", "US": "R", "GB": "15", "DE": "16"},
    "releases": [
        {"country": "FR", "type": "cinema", "certification": "12"},
        {"country": "DE", "type": "cinema", "certification": "16"},
        {"country": "GB", "type": "cinema", "certification": "15"},
        {"country": "US", "type": "cinema", "certification": "R"},
        {"country": "US", "type": "digital", "certification": "R"},
    ],
}


def test_other_countries_count_too_when_the_administrator_says_so() -> None:
    assert title_age(RESIDENT_EVIL, None, "FR") == 12  # the portal's country alone
    assert title_age(RESIDENT_EVIL, None, "FR", also=("GB",)) == 15
    assert title_age(RESIDENT_EVIL, None, "FR", also=("GB", "US")) == 17  # the strictest wins
    assert title_age(RESIDENT_EVIL, None, "FR", also=("JP",)) == 12  # a country that does not rate it


def test_another_country_is_rated_by_the_same_order() -> None:
    # Mad Max in the United States: R everywhere; its French TV rating (12) and the other's R: 17
    assert title_age(MAD_MAX, "fr/TP", "FR", also=("US",)) == 17
    # only a certification known for that country (details from before every release was kept)
    assert title_age({"certifications": {"FR": "TP", "US": "R"}}, "fr/TP", "FR", also=("US",)) == 17


def test_the_average_of_every_country() -> None:
    data = {
        "releases": [
            {"country": "FR", "type": "tv", "certification": "12"},
            {"country": "US", "type": "cinema", "certification": "R"},
            {"country": "GB", "type": "cinema", "certification": "15"},
        ]
    }
    assert title_age(data, None, "FR") == 12  # the portal's country alone
    assert title_age(data, None, "FR", blend="average") == 15  # (12 + 17 + 15) / 3: 14.7 → 15
    assert title_age({}, None, "FR", blend="average") is None  # nothing rated: unrated still


def test_warnings_are_read_by_family() -> None:
    data = {
        "releases": [
            {"country": "FR", "type": "tv", "certification": "12", "descriptors": ["Violence"]},
            {"country": "DE", "type": "cinema", "certification": "16", "descriptors": ["threat"]},
            {"country": "US", "type": "cinema", "certification": "R", "descriptors": ["Strong language"]},
            {"country": "NL", "type": "cinema", "certification": "12", "descriptors": ["s", "d"]},
        ]
    }
    assert warnings_of(data) == {"violence", "fear", "language", "sex", "drugs"}
    assert warnings_of({}) == set()
