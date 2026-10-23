"""Issue 229: a card's colour by its work's genre."""

from portalab.modules.cards.family import family_of


def test_a_works_colour() -> None:
    assert family_of(["Aventure", "Drame", "Science-Fiction"]) == "sf"  # one strong genre
    assert family_of(["Action", "Thriller", "Science-Fiction"]) == "multi"  # several: gold
    assert family_of(["Animation", "Action", "Science-Fiction"]) == "family"  # drawn first
    assert family_of(["Aventure", "Drame"]) == "action"  # gentle genres: the first that has a colour
    assert family_of(["Comédie", "Romance"]) == "family"
    assert family_of(["Drame", "Histoire"]) == "drama"
    assert family_of(["Horreur"]) == "dark"
    assert family_of([]) == "drama"
