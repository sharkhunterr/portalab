"""Issue 189 — the « Leaderboard » widget: the first ten of the board, my place apart, how many are ranked;
« level » only all time; nothing ranked: no data; 013 away: unavailable."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.modules.community.integrations import LeaderboardWidget
from portalab.modules.community.leaderboards.view import BoardView, RankedMember

CTX = LocaleContext(locale="en", time_zone="UTC")


@dataclass
class FakeBoards:
    view: BoardView
    asked: list[tuple[str, str]] = field(default_factory=list)

    def metrics(self) -> list[str]:
        return ["xp", "level"]

    async def board(self, viewer: Any, metric: str, period: str, *, limit: int = 50) -> BoardView:
        self.asked.append((metric, period))
        return self.view


def _member(rank: int, me: bool = False) -> RankedMember:
    return RankedMember(rank=rank, user_id=uuid4(), display_name=f"m{rank}", score=100 - rank, me=me)


async def test_the_first_ten_my_place_and_how_many() -> None:
    entries = [_member(r, me=r == 12) for r in range(1, 15)]
    boards = FakeBoards(BoardView("xp", "month", "available", entries=entries, me=entries[11]))
    payload = await LeaderboardWidget(boards).load(Principal(user_id=uuid4()), {"period": "month"}, CTX)
    assert payload.state == "available"
    assert len(payload.data["entries"]) == 10
    assert payload.data["me"]["rank"] == 12
    assert payload.data["total"] == 14


async def test_level_is_all_time_and_empty_is_no_data() -> None:
    boards = FakeBoards(BoardView("level", "all", "available"))
    payload = await LeaderboardWidget(boards).load(
        Principal(user_id=uuid4()), {"metric": "level", "period": "week"}, CTX
    )
    assert boards.asked == [("level", "all")]
    assert payload.state == "no-data"


@pytest.mark.parametrize("metric", ["coins", "xp"])
async def test_unavailable(metric: str) -> None:
    boards = FakeBoards(BoardView("xp", "all", "unavailable"))
    payload = await LeaderboardWidget(boards).load(Principal(user_id=uuid4()), {"metric": metric}, CTX)
    assert payload.state == "unavailable"
