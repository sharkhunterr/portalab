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


# issue 295: a card's genre frame is its work's main genre (the first it is given), one frame each — a series'
# combined genres taken as the film's they read as, the rare ones as the closest
GENRES = (
    "action",
    "adventure",
    "animation",
    "comedy",
    "crime",
    "documentary",
    "drama",
    "family",
    "fantasy",
    "history",
    "horror",
    "music",
    "mystery",
    "romance",
    "sf",
    "thriller",
    "war",
    "western",
)
MAIN = {
    "action": "action",
    "action & adventure": "action",
    "aventure": "adventure",
    "animation": "animation",
    "comédie": "comedy",
    "crime": "crime",
    "documentaire": "documentary",
    "news": "documentary",
    "reality": "documentary",
    "talk": "documentary",
    "drame": "drama",
    "soap": "drama",
    "téléfilm": "drama",
    "familial": "family",
    "kids": "family",
    "fantastique": "fantasy",
    "histoire": "history",
    "horreur": "horror",
    "musique": "music",
    "mystère": "mystery",
    "romance": "romance",
    "science-fiction": "sf",
    "science-fiction & fantastique": "sf",
    "thriller": "thriller",
    "guerre": "war",
    "war & politics": "war",
    "western": "western",
}


def genre_of(genres: Sequence[str]) -> str:
    """The work's main genre: its first one known, drama when it has none."""
    names = [g.strip().lower() for g in genres if g and g.strip()]
    return next((MAIN[n] for n in names if n in MAIN), "drama")


# issue 296: the themes a theme booster draws among, the most telling first (a work's own theme, the scene its
# booster opens in, is its first): Japanese animation, giant monsters and robots, samurai and ninjas, Japan
THEMES = ("anime", "kaiju", "samurai", "japan")
KAIJU = frozenset({"kaiju", "giant monster", "giant robot", "mecha", "godzilla"})
SAMURAI = frozenset({"samurai", "ninja", "ronin", "yakuza", "katana", "shogun", "feudal japan", "jidaigeki"})
# set in Japan: its keywords say so, or samurai, yakuzas do (a katana or a ninja may be anywhere)
JAPAN = frozenset({"japan", "japanese", "anime", "japanese mythology", "post war japan"}) | (
    SAMURAI - {"katana", "ninja"}
)


def themes_of(
    countries: Sequence[str], languages: Sequence[str], keywords: Sequence[str], animated: bool
) -> list[str]:
    """A work's themes: Japanese when made in Japan in Japanese (a production country alone says little — a
    Hollywood film co-produced there is not) or when its keywords set it there; the others by its keywords."""
    words = {k.strip().casefold() for k in keywords if k and k.strip()}
    japanese = "JP" in countries and any(lang.strip().casefold() == "japanese" for lang in languages)
    found = {
        "anime": "anime" in words or (japanese and animated),
        "kaiju": bool(words & KAIJU),
        "samurai": bool(words & SAMURAI),
        "japan": japanese or bool(words & JAPAN),
    }
    return [theme for theme in THEMES if found[theme]]
