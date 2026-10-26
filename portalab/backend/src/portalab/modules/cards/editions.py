"""Issue 233: a card's edition, like a trading card game's — the medium and the look of its work's era of
release. Issue 255: fourteen generations, from the silent film's intertitle to today's glass: each card has,
besides its own versions, its edition's: its edition's frame (drawn by a visual pack's ``card_frame``,
Portalab drawing the card) with the edition's symbol on its band, foil or not — and, for a legendary, its HD
version."""

# the editions in order: their key, the last year of release they hold (the last one: every year since)
EDITIONS: tuple[tuple[str, int | None], ...] = (
    ("nitrate", 1929),
    ("noir", 1949),
    ("drivein", 1959),
    ("super8", 1969),
    ("film", 1979),
    ("laserdisc", 1985),
    ("vhs", 1992),
    ("zine", 1997),
    ("bubble", 2002),
    ("disc", 2008),
    ("leather", 2012),
    ("tiles", 2016),
    ("stream", 2021),
    ("glass", None),
)


def edition_of(year: int | None) -> str | None:
    """The edition of a work released in ``year`` (none without a year)."""
    if year is None:
        return None
    return next(key for key, last in EDITIONS if last is None or year <= last)
