"""Issue 362 — Hardcover, the community book database: an author found by their name (not a namesake),
their books readers know once each, with covers from Hardcover's image host only; the library's books
identified (an edition's ISBN, Hardcover's slug, an edition's title by the same author); a series' volumes,
one per whole position, told by the original's id; a series told apart from its namesakes by the library's
own volumes; the token pasted with or without its prefix."""

import json

import httpx

from portalab.capabilities.media import BOOK_SERIES, PEOPLE, OwnedBook
from portalab.connectors.hardcover import HardcoverConnector, author_names, fold, image_ref, languages
from tests.contract.connectors.builtin_fixtures import handle_for


async def test_an_author_and_their_books() -> None:
    seen: list[httpx.Request] = []
    connector = HardcoverConnector()
    provider = connector.provider(PEOPLE, handle_for("hardcover", seen=seen))
    record = await provider.person("robin hobb", {}, "fr")
    assert record is not None and record.ids == {"hardcover": "204214"} and record.name == "Robin Hobb"
    assert record.biography == "An American writer." and record.birthday == "1952-03-05"
    assert record.portrait == "/author/204214/photo.jpeg"
    [apprentice, royal] = record.credits  # the same book twice: once; a translation few read left out
    assert (apprentice.kind, apprentice.tmdb_id, apprentice.year) == ("book", "101", 1995)
    assert apprentice.vote_average == 8.2 and apprentice.popularity == 9000
    assert apprentice.poster == "/edition/1/apprentice.jpg"
    assert apprentice.title == "L'Apprenti assassin" and royal.title == "Royal Assassin"  # #371: in French
    assert royal.poster is None  # an image elsewhere than Hardcover's host is never fetched
    # the token, pasted with its « Bearer » prefix, sent once; the portal says who it is
    assert seen[0].headers["authorization"] == "Bearer hardcover-secret-token"
    assert "Portalab" in seen[0].headers["user-agent"]
    assert json.loads(seen[0].content)["variables"] == {"query": "robin hobb", "type": "author", "per": 5}
    assert await provider.person("Nobody At All", {}, "fr") is None


async def test_the_library_s_books_identified() -> None:
    seen: list[httpx.Request] = []
    provider = HardcoverConnector().provider(BOOK_SERIES, handle_for("hardcover", seen=seen))
    found = await provider.identify(
        [
            OwnedBook(
                "a", "L'Apprenti assassin", ("Robin Hobb",), {"isbn": ["978-0553573398"], "asin": ["X"]}
            ),
            OwnedBook("b", "L'assassin du roi", ("Robin_Hobb",), {"hardcover": ["royal-assassin"]}),
            OwnedBook("c", "La Nef du crépuscule", ("Hobb,Robin",)),
            OwnedBook("d", "Nothing like it", ("Robin Hobb",)),
        ]
    )
    # a translation's edition: the original it was merged into
    assert {key: [c.tmdb_id for c in credits] for key, credits in found.items()} == {
        "a": ["101"],
        "b": ["102"],
        "c": ["103"],  # not the same title by someone else
    }
    # #371: a part (3.1) of a longer book, told with the whole book at its place (3), not a namesake
    assert found["c"][0].part_of == "149300" and found["a"][0].part_of is None
    asked = [json.loads(r.content) for r in seen]
    by_title = next(a["variables"] for a in asked if "query ByTitle" in a["query"])
    assert by_title["authors"] == ["Hobb,Robin", "Robin Hobb"]  # as the library writes it, and as Hardcover
    assert {"title": {"_ilike": "La Nef du crépuscule"}} in by_title["titles"]
    # asked once: kept
    count = len(seen)
    await provider.identify([OwnedBook("c", "La Nef du crépuscule", ("Hobb,Robin",))])
    assert len(seen) == count


async def test_a_series_is_the_one_holding_the_library_s_volumes() -> None:
    provider = HardcoverConnector().provider(BOOK_SERIES, handle_for("hardcover"))
    found = await provider.series("L'Assassin royal", ["101", "103"])
    assert found is not None and found.name == "L'Assassin royal" and found.author == "Robin Hobb"
    # one per whole place: the featured single volume, by the original's id, under the series' own title
    assert [(v.tmdb_id, v.title, v.position) for v in found.volumes] == [
        ("101", "L'Apprenti assassin", 1.0),
        ("102", "L'Assassin du roi", 2.0),
        ("103", "La Nef du crépuscule", 3.0),  # a split part: a volume of the translation
    ]
    # none of the library's: the series named exactly so with the most volumes, else none
    farseer = await provider.series("Farseer", [])
    assert farseer is not None and farseer.ids == {"hardcover": "7"}
    assert await provider.series("Unknown series", []) is None


async def test_a_book_s_sheet() -> None:
    """#367: a book's description, authors (not its narrator), series, readers' genres and moods, its rating
    out of 10, its editions (the empty ones left out, an audiobook's told), a merged duplicate's original."""
    provider = HardcoverConnector().provider(BOOK_SERIES, handle_for("hardcover"))
    book = await provider.book("102")
    assert book is not None and (book.ref, book.title, book.pages, book.year) == (
        "101",
        "Assassin's Apprentice",
        435,
        1995,
    )
    assert book.authors == ["Robin Hobb"] and book.series == [
        ("Farseer", 1.0),
        ("The Realm of the Elderlings", None),
    ]
    assert book.genres == ["Epic", "Fantasy"] and book.moods == ["adventurous"]
    assert (book.rating, book.votes, book.readers) == (8.2, 3000, 9000)
    assert book.cover == "/edition/1/apprentice.jpg"
    french, audio = book.editions
    assert (french.title, french.language, french.format, french.year) == (
        "L'Apprenti assassin",
        "fr",
        "Read",
        1998,
    )
    assert (
        french.ids == {"isbn": ["9782290302512"]} and french.publisher == "J'ai Lu" and french.cover is None
    )
    assert audio.audio and audio.ids == {"asin": ["B00AUDIO01"]}
    assert await provider.book("999") is None
    assert await provider.book("not-a-number") is None
    # #369: the service's edition languages — those alone, in their order
    english = HardcoverConnector().provider(
        BOOK_SERIES, handle_for("hardcover", config={"languages": "en, fr"})
    )
    shown = await english.book("101")
    assert shown is not None and [e.language for e in shown.editions] == ["en", "fr"]
    german = HardcoverConnector().provider(BOOK_SERIES, handle_for("hardcover", config={"languages": "de"}))
    assert (await german.book("101")).editions == []  # type: ignore[union-attr]
    assert languages(" FR , en,fr ") == ["fr", "en"] and languages("") == []


def test_names_and_images() -> None:
    assert fold("Robin  HOBB") == fold("robin hobb") == "robin hobb"
    assert fold("Émile Zola") == "emile zola"
    assert author_names(["King,Stephen", "Robin_Hobb"]) == [
        "King,Stephen",
        "Stephen King",
        "Robin_Hobb",
        "Robin Hobb",
    ]
    assert image_ref({"url": "https://assets.hardcover.app/edition/1/a.jpg"}) == "/edition/1/a.jpg"
    assert image_ref("https://assets.hardcover.app/../etc/passwd") is None
    assert image_ref("https://assets.hardcover.app.evil.example/a.jpg") is None
    assert image_ref(None) is None
