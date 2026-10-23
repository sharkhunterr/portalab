"""Issue 229: a card's colour is its work's genre — like a trading card game's colours, the same for films,
series, books and games. A drawn work is « family »; one strong genre gives its colour, two or more strong
ones gold (« multi »); with none, the first gentle genre decides (an adventure is action's, a comedy family's,
anything else drama's)."""

from collections.abc import Sequence

FAMILIES = ("sf", "action", "fantasy", "family", "drama", "dark", "multi")
STRONG = {
    "science-fiction": "sf",
    "science-fiction & fantastique": "sf",
    "fantastique": "fantasy",
    "horreur": "dark",
    "thriller": "dark",
    "crime": "dark",
    "mystère": "dark",
    "action": "action",
    "action & adventure": "action",
    "guerre": "action",
    "war & politics": "action",
    "western": "action",
}
DRAWN = {"animation", "kids"}
GENTLE = {"aventure": "action", "comédie": "family", "familial": "family"}


def family_of(genres: Sequence[str]) -> str:
    names = [g.strip().lower() for g in genres if g and g.strip()]
    if any(n in DRAWN for n in names):
        return "family"
    strong = list(dict.fromkeys(STRONG[n] for n in names if n in STRONG))
    if len(strong) == 1:
        return strong[0]
    if len(strong) > 1:
        return "multi"
    return next((GENTLE[n] for n in names if n in GENTLE), "drama")
