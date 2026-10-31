"""Issue 229: a card's colour by its work's genre."""

from portalab.modules.cards.family import GENRES, MAIN, family_of, genre_of


def test_a_works_colour() -> None:
    assert family_of(["Aventure", "Drame", "Science-Fiction"]) == "sf"  # one strong genre
    assert family_of(["Aventure", "Action", "Science-Fiction"]) == "sf"  # several: the one that marks it most
    assert family_of(["Science-Fiction", "Horreur"]) == "dark"
    assert family_of(["Action", "Fantastique"]) == "fantasy"
    assert family_of(["Animation", "Action", "Science-Fiction"]) == "family"  # drawn first
    assert family_of(["Aventure", "Drame"]) == "action"  # gentle genres: the first that has a colour
    assert family_of(["Comédie", "Romance"]) == "family"
    assert family_of(["Drame", "Histoire"]) == "drama"
    assert family_of(["Horreur"]) == "dark"
    assert family_of(["Action", "Thriller"]) == "action"  # a thriller is dark only on its own
    assert family_of(["Drame", "Thriller"]) == "dark"
    assert family_of([]) == "drama"


def test_a_works_genre_frame_is_its_main_genre() -> None:
    # issue 295: the first genre it is given, one frame each
    assert genre_of(["Horreur", "Thriller"]) == "horror"
    assert genre_of(["Thriller", "Horreur"]) == "thriller"
    assert genre_of(["Comédie", "Romance"]) == "comedy"
    assert genre_of(["Science-Fiction & Fantastique", "Drame"]) == "sf"
    assert genre_of(["War & Politics"]) == "war"
    # an unknown one is passed over; none at all: drama
    assert genre_of(["Inconnu", "Western"]) == "western"
    assert genre_of([]) == "drama"
    assert set(MAIN.values()) == set(GENRES)
