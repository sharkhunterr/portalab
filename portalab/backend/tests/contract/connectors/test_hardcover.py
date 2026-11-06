"""Issue 362 — Hardcover, the community book database: an author found by their name (not a namesake),
their books once each with their editions' ISBNs and covers from Hardcover's image host only; a series
told apart from its namesakes by the library's own ISBNs; the token pasted with or without its prefix."""

import json

import httpx

from portalab.capabilities.media import BOOK_SERIES, PEOPLE
from portalab.connectors.hardcover import HardcoverConnector, fold, image_ref
from tests.contract.connectors.builtin_fixtures import handle_for


async def test_an_author_and_their_books() -> None:
    seen: list[httpx.Request] = []
    connector = HardcoverConnector()
    provider = connector.provider(PEOPLE, handle_for("hardcover", seen=seen))
    record = await provider.person("robin hobb", {}, "fr")
    assert record is not None and record.ids == {"hardcover": "204214"} and record.name == "Robin Hobb"
    assert record.biography == "An American writer." and record.birthday == "1952-03-05"
    assert record.portrait == "/author/204214/photo.jpeg"
    [apprentice, royal] = record.credits  # the same book twice: once
    assert (apprentice.kind, apprentice.tmdb_id, apprentice.year) == ("book", "101", 1995)
    assert apprentice.isbns == ("9780553573398", "0553573403")  # an invalid ISBN left out
    assert apprentice.vote_average == 8.2 and apprentice.popularity == 9000
    assert apprentice.poster == "/edition/1/apprentice.jpg"
    assert royal.poster is None  # an image elsewhere than Hardcover's host is never fetched
    # the token, pasted with its « Bearer » prefix, sent once; the portal says who it is
    assert seen[0].headers["authorization"] == "Bearer hardcover-secret-token"
    assert "Portalab" in seen[0].headers["user-agent"]
    assert json.loads(seen[0].content)["variables"] == {"query": "robin hobb", "type": "author", "per": 5}
    assert await provider.person("Nobody At All", {}, "fr") is None


async def test_a_series_is_the_one_holding_the_library_s_volumes() -> None:
    provider = HardcoverConnector().provider(BOOK_SERIES, handle_for("hardcover"))
    found = await provider.series("L'Assassin royal", ["978-0553573398"])
    assert found is not None and found.name == "The Farseer Trilogy" and found.author == "Robin Hobb"
    assert [(v.title, v.position) for v in found.volumes] == [
        ("Assassin's Apprentice", 1.0),
        ("Royal Assassin", 2.0),
    ]
    # no ISBN in common: the series named exactly so, else none
    assert (await provider.series("Farseer", [])).name == "Farseer"
    assert await provider.series("Unknown series", []) is None


def test_names_and_images() -> None:
    assert fold("Robin  HOBB") == fold("robin hobb") == "robin hobb"
    assert fold("Émile Zola") == "emile zola"
    assert image_ref({"url": "https://assets.hardcover.app/edition/1/a.jpg"}) == "/edition/1/a.jpg"
    assert image_ref("https://assets.hardcover.app/../etc/passwd") is None
    assert image_ref("https://assets.hardcover.app.evil.example/a.jpg") is None
    assert image_ref(None) is None
