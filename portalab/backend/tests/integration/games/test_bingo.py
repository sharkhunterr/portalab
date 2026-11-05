"""Issue 356 — the month's media bingo: one card for every member, drawn on the month's first visit from the
squares the library can fill (4 x 4, or 3 x 3 for a small library); a square ticks itself from what the
services tell; each line and the full card told once to the reward rules; the lines on a board; a member's
lines exported and erased with them."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from portalab.capabilities.media_core import BingoCell, BingoTick
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.games.bingo import NoBingo, draw, lines
from portalab.modules.games.participant import GamesParticipant
from tests.integration.games.test_games import NOW, _module, _users

pytestmark = pytest.mark.integration

CELLS = [
    *(BingoCell(f"genre:{g}", "genre") for g in ("comedy", "drama", "horror", "scifi", "animation", "crime")),
    *(BingoCell(f"era:{e}", "era") for e in ("1980", "1990", "recent")),
    *(BingoCell(f"country:{c}", "country") for c in ("FR", "JP", "GB")),
    BingoCell("length:long", "length"),
    BingoCell("series:pilot", "series"),
    *(BingoCell(f"kind:{k}", "kind") for k in ("book", "audiobook", "game", "live")),
    BingoCell("review", "community"),
    BingoCell("later", "community"),
]


def test_a_month_s_card_is_drawn_the_same_for_everyone() -> None:
    month = date(2026, 11, 1)
    card = draw(CELLS, month)
    assert card == draw(list(reversed(CELLS)), month) and len(card) == 16
    assert len({c["key"] for c in card}) == 16
    groups = [c["group"] for c in card]
    assert groups.count("genre") >= 5 and groups.count("community") >= 1 and groups.count("kind") >= 3
    assert draw(CELLS, date(2026, 12, 1)) != card  # a new card each month
    assert len(draw(CELLS[:10], month)) == 9  # a small library: 3 x 3
    assert draw(CELLS[:8], month) == []
    assert len(lines(4)) == 10 and lines(3)[-1] == ("diag:1", (2, 4, 6))


async def test_the_month_s_bingo(database: Database) -> None:
    zoe, alex = await _users(database, "zoe", "alex")
    module, games, events, _ = _module(database, FixedClock(NOW))
    ticked: dict[UUID, dict[str, BingoTick]] = {}

    async def cells(*, year: int) -> list[BingoCell]:
        assert year == NOW.year
        return CELLS

    async def ticks(
        keys: list[str], since: datetime, until: datetime, *, user: UUID | None = None
    ) -> dict[UUID, dict[str, BingoTick]]:
        assert since <= NOW < until and until - since >= timedelta(days=28)
        return {u: dict(t) for u, t in ticked.items() if user is None or u == user}

    games.bingo_cells = cells  # type: ignore[attr-defined]
    games.bingo_ticks = ticks  # type: ignore[attr-defined]

    first = await module.bingo.view(zoe)
    assert first["month"] == "2026-10-01" and first["size"] == 4 and len(first["cells"]) == 16
    assert first["squares"] == 0 and not any(line["done"] for line in first["lines"])
    keys = [c["key"] for c in first["cells"]]
    film = uuid4()
    tick = BingoTick(film, "Alien", None, NOW - timedelta(days=2))
    ticked[zoe] = {key: tick for key in keys[:4]}  # the first row
    mine = await module.bingo.view(zoe)
    assert [c["key"] for c in mine["cells"]] == keys  # the same card all month
    assert mine["squares"] == 4 and mine["done_lines"] == 1 and not mine["card"]
    assert mine["cells"][0]["by"] == {
        "id": str(film),
        "title": "Alien",
        "image_id": None,
        "at": tick.at.isoformat(),
    }
    assert [line["key"] for line in mine["lines"] if line["done"]] == ["row:0"]
    await module.bingo.view(zoe)  # told once
    told = [(t, m) for t, m, _ in events.told if t.startswith("games.bingo")]
    assert told == [("games.bingo_line", {"month": "2026-10-01", "line": "row:0", "lines": 1})]

    ticked[alex] = {key: tick for key in keys}  # alex filled the card: 10 lines and the card
    assert await module.bingo.check() == 11
    assert await module.bingo.check() == 0
    assert [m for t, m, _ in events.told if t == "games.bingo_card"] == [
        {"month": "2026-10-01", "squares": 16}
    ]
    seen = await module.bingo.view(zoe)
    assert seen["players"] == 2 and seen["cards"] == 1
    board = await module.boards.board(alex, "bingo", "month")
    assert board["me"]["value"] == 10

    exported = [r for r in await GamesParticipant(database).export(alex) if r.category == "games.bingo"]
    assert len(exported) == 11
    await GamesParticipant(database).erase(alex, "final")
    assert [r for r in await GamesParticipant(database).export(alex) if r.category == "games.bingo"] == []


async def test_no_bingo_without_enough_squares_or_when_switched_off(database: Database) -> None:
    (zoe,) = await _users(database, "zoe")
    module, games, _, _ = _module(database, FixedClock(datetime(2026, 9, 3, tzinfo=UTC)))

    async def cells(*, year: int) -> list[BingoCell]:
        return CELLS[:5]

    games.bingo_cells = cells  # type: ignore[attr-defined]
    with pytest.raises(NoBingo):
        await module.bingo.view(zoe)
    assert await module.bingo.check() == 0
    module.config.bingo.enabled = False
    assert "bingo" not in module.config.enabled_games()
