"""Issue 229: a card's colour by its work's genre."""

from portalab.modules.cards.family import family_of


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
