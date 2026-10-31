"""#299 — the library titles and people a text names: a title however it is written (accents, case), the
longest first (not « Star Wars » inside « Star Wars : Les Derniers Jedi »), a credited person by their full
name; never a one-word short title (« Up ») nor a one-word name."""

from fastapi import FastAPI

from portalab.capabilities.media.testkit import library_record
from portalab.modules.media.mentions import LibraryMentions
from tests.integration.media.conftest import MediaHarness, users


async def test_a_text_names_library_titles_and_people(app: FastAPI, media: MediaHarness) -> None:
    await users(app, media, "zoe")
    library = media.service(1, "fake")
    media.library(library)
    await media.module.library.upsert(
        [
            library_record("m1", title="Dune : Deuxième partie", year=2024, directors=["Denis Villeneuve"]),
            library_record("m2", title="Star Wars", year=1977),
            library_record("m3", title="Star Wars : Les Derniers Jedi", year=2017),
            library_record("m4", title="Up", year=2009, directors=["Pete Docter"]),
            library_record("m5", title="Interstellar", year=2014),
        ],
        library,
    )
    found = await LibraryMentions(media.database).mentions(
        [
            "DUNE : DEUXIÈME PARTIE en 4K — un film de Denis Villeneuve",
            "Star Wars : les derniers Jedi revient, et Interstellar aussi",
            "Things went up for Docter's next film",
            "Rien à voir",
        ]
    )
    labels = [[m.label for m in mentions] for mentions in found]
    assert labels[0] == ["Dune : Deuxième partie", "Denis Villeneuve"]
    assert labels[1] == ["Star Wars : Les Derniers Jedi", "Interstellar"]
    assert labels[2] == [] and labels[3] == []
    person = found[0][1]
    assert person.kind == "person" and person.route == "/media/people/Denis%20Villeneuve"
