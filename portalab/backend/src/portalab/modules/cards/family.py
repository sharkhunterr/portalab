"""Issue 229: a card's colour is its work's genre — like a trading card game's colours, the same for films,
series, books and games. A drawn work is « family »; a strong genre gives its colour — several, the one
that marks a work the most (dark, then science fiction, fantasy, action: a space horror is dark, a space war
science fiction); with none, the first gentle genre decides (an adventure is action's, a comedy family's,
anything else drama's). No gold body: gold is a rarity's."""

from collections.abc import Sequence

FAMILIES = ("sf", "action", "fantasy", "family", "drama", "dark")
FIRST = ("dark", "sf", "fantasy", "action")  # several strong genres: the first of these
STRONG = {
    "science-fiction": "sf",
    "science-fiction & fantastique": "sf",
    "fantastique": "fantasy",
    "horreur": "dark",
    "crime": "dark",
    "action": "action",
    "action & adventure": "action",
    "guerre": "action",
    "war & politics": "action",
    "western": "action",
}
DRAWN = {"animation", "kids"}
GENTLE = {  # a thriller or a mystery is dark only when nothing stronger marks it (an action thriller: action)
    "aventure": "action",
    "thriller": "dark",
    "mystère": "dark",
    "comédie": "family",
    "familial": "family",
}


def family_of(genres: Sequence[str]) -> str:
    names = [g.strip().lower() for g in genres if g and g.strip()]
    if any(n in DRAWN for n in names):
        return "family"
    strong = {STRONG[n] for n in names if n in STRONG}
    if strong:
        return next(f for f in FIRST if f in strong)
    return next((GENTLE[n] for n in names if n in GENTLE), "drama")
