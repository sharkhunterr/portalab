"""Issue 233: a card's edition, like a trading card game's — the medium of its work's era of release: the
cinema's film reel, the video shop's cassette, the disc, then streaming. Each card has, besides its own
versions, its edition's: its edition's frame (drawn by a visual pack's ``card_frame``, Portalab drawing the
card) with the edition's symbol on its band, foil or not."""

# the editions in order: their key, the last year of release they hold (the last one: every year since)
EDITIONS: tuple[tuple[str, int | None], ...] = (
    ("film", 1979),
    ("vhs", 1996),
    ("disc", 2009),
    ("stream", None),
)


def edition_of(year: int | None) -> str | None:
    """The edition of a work released in ``year`` (none without a year)."""
    if year is None:
        return None
    return next(key for key, last in EDITIONS if last is None or year <= last)
