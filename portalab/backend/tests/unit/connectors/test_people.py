"""#92 — a person as TMDB serves them, and as Seerr serves TMDB's people (camel-cased): one record."""

from portalab.connectors.tmdb.people import map_person, same_name, snake

RSQ = "\u2019"  # the typographic apostrophe

TMDB = {
    "id": 500,
    "name": "Tom Cruise",
    "biography": "An actor.",
    "birthday": "1962-07-03",
    "place_of_birth": "Syracuse, New York, USA",
    "known_for_department": "Acting",
    "profile_path": "/tom.jpg",
    "popularity": 42.5,
    "external_ids": {"imdb_id": "nm0000129"},
    "combined_credits": {
        "cast": [
            {
                "id": 954,
                "media_type": "movie",
                "title": "Mission: Impossible",
                "character": "Ethan Hunt",
                "release_date": "1996-05-22",
                "poster_path": "/mi.jpg",
                "vote_count": 9000,
                "vote_average": 7,
            },
            {"id": 77, "media_type": "tv", "name": "A talk show", "character": "", "episode_count": 1},
            {"id": 1, "media_type": "person", "name": "not a title"},
        ],
        "crew": [
            {
                "id": 954,
                "media_type": "movie",
                "title": "Mission: Impossible",
                "job": "Producer",
                "department": "Production",
                "release_date": "1996-05-22",
            },
        ],
    },
}


def test_a_tmdb_person() -> None:
    person = map_person(TMDB)
    assert person.ids == {"tmdb": "500", "imdb": "nm0000129"}
    assert (person.birthday, person.place_of_birth, person.known_for) == (
        "1962-07-03",
        "Syracuse, New York, USA",
        "Acting",
    )
    assert person.portrait == "/tom.jpg"
    assert [(c.title, c.department, c.role, c.year) for c in person.credits] == [
        ("Mission: Impossible", "cast", "Ethan Hunt", 1996),
        ("Mission: Impossible", "production", "Producer", 1996),
    ]  # the talk show and the non-title are left out


def test_seerr_camel_case_is_the_same_person() -> None:
    camel = {
        "id": 500,
        "name": "Tom Cruise",
        "placeOfBirth": "Syracuse, New York, USA",
        "knownForDepartment": "Acting",
        "profilePath": "/tom.jpg",
    }
    credits = {
        "cast": [
            {
                "id": 954,
                "mediaType": "movie",
                "title": "Mission: Impossible",
                "character": "Ethan Hunt",
                "releaseDate": "1996-05-22",
                "voteCount": 9000,
            }
        ]
    }
    person = map_person({**snake(camel), "combined_credits": snake(credits)})
    assert person.place_of_birth == "Syracuse, New York, USA" and person.known_for == "Acting"
    assert [(c.title, c.year, c.vote_count) for c in person.credits] == [("Mission: Impossible", 1996, 9000)]


def test_names_compare_without_case_accents_or_apostrophes() -> None:
    assert same_name(f"Chris O{RSQ}Dowd") == same_name("chris o'dowd") == "chris o dowd"
    assert same_name("Michèle Laroque") == "michele laroque"


def test_a_grimmory_audiobook_tells_everything_it_knows() -> None:
    """#92: the description, the narrator apart from the authors, the length, the readers' rating and the
    Audible id — Grimmory has them all (its list carries descriptions only when asked)."""
    from portalab.connectors.grimmory import map_book

    _, kind, payload = map_book(
        {
            "id": 1245,
            "primaryFile": {"bookType": "AUDIOBOOK"},
            "metadata": {
                "title": "Alien - La sortie des profondeurs",
                "description": "Un vaisseau minier…",
                "authors": ["Tim Lebbon", "Dirk Maggs"],
                "narrator": "Jean Dupont",
                "asin": "B06XXXXXX1",
                "audibleRating": 4.3,
                "audiobookMetadata": {"durationSeconds": 21600},
            },
        }
    ) or (None, None, {})
    assert kind == "audiobook"
    assert payload["overview"] == "Un vaisseau minier…"
    assert payload["authors"] == ["Tim Lebbon", "Dirk Maggs"] and payload["narrators"] == ["Jean Dupont"]
    assert payload["duration_s"] == 21600.0 and payload["rating"] == 8.6
    assert payload["ids"] == {"asin": "B06XXXXXX1"}
