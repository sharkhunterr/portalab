"""Issue 356: the month's media bingo — the same card for every member, drawn on the month's first visit from
the squares the library can fill (a genre, an era, a country, a film's length, a series' pilot, a book, an
audiobook, a game, live TV, a review…): 4 x 4, or 3 x 3 for a small library. Nothing to declare: a square
ticks itself when the member's services tell they finished a title that fits it this month (the media's
side, ``GameSources.bingo_ticks``). Each line completed (a row, a column, a diagonal) is told once
(``games.bingo_line``), and the full card (``games.bingo_card``) — the reward rules turn them into XP, coins
or a booster. A new card each month, in the economy's time zone."""

import random
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.media_core import GAME_SOURCES, BingoCell, BingoTick, GameSources
from portalab.core.db import Database
from portalab.core.errors import Unavailable
from portalab.core.event_port import SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.games.common import GameClosed, Shared
from portalab.modules.games.events import BINGO_CARD, BINGO_LINE
from portalab.modules.games.models import BingoCard, BingoDone

GAME = "bingo"
CARD = "card"
# what a 4 x 4 card is made of, group by group; the square left goes to any group
QUOTAS = (
    ("genre", 5),
    ("era", 2),
    ("country", 2),
    ("length", 1),
    ("series", 1),
    ("kind", 3),
    ("community", 1),
)


class NoBingo(Unavailable):
    default_code = "games.bingo_unavailable"
    default_title = "The library cannot fill a bingo card"


def lines(size: int) -> list[tuple[str, tuple[int, ...]]]:
    """A card's lines: its rows, its columns and its two diagonals (squares in reading order)."""
    rows = [(f"row:{r}", tuple(r * size + c for c in range(size))) for r in range(size)]
    cols = [(f"col:{c}", tuple(r * size + c for r in range(size))) for c in range(size)]
    diagonals = [
        ("diag:0", tuple(i * size + i for i in range(size))),
        ("diag:1", tuple(i * size + size - 1 - i for i in range(size))),
    ]
    return rows + cols + diagonals


def draw(cells: Sequence[BingoCell], month: date) -> list[dict[str, str]]:
    """The month's card from the squares the library can fill — the same whoever draws it first."""
    rng = random.Random(f"bingo:{month.isoformat()}")  # noqa: S311 — a game's draw, not a secret
    size = 4 if len(cells) >= 16 else 3 if len(cells) >= 9 else 0
    if not size:
        return []
    groups: dict[str, list[BingoCell]] = {}
    for cell in sorted(cells, key=lambda c: c.key):
        groups.setdefault(cell.group, []).append(cell)
    for members in groups.values():
        rng.shuffle(members)
    chosen: list[BingoCell] = []
    scale = size * size / 16
    for group, quota in QUOTAS:
        chosen += groups.get(group, [])[: max(1, round(quota * scale))]
    chosen = chosen[: size * size]
    rest = [c for c in sorted(cells, key=lambda c: c.key) if c not in chosen]
    rng.shuffle(rest)
    chosen += rest[: size * size - len(chosen)]
    rng.shuffle(chosen)
    return [{"key": c.key, "group": c.group} for c in chosen]


class Bingo:
    def __init__(self, database: Database, shared: Shared, *, clock: Clock | None = None) -> None:
        self.database = database
        self.shared = shared
        self.clock = clock

    def _sources(self) -> GameSources:
        providers = self.shared.capabilities.system_providers(GAME_SOURCES)
        if not providers:
            raise NoBingo("The library cannot be read.")
        return cast(GameSources, providers[0].provider)

    def _open(self) -> bool:
        return GAME in self.shared.config().enabled_games()

    async def _month(self, at: datetime) -> tuple[date, datetime, datetime]:
        """The month's first day, and when it starts and ends (UTC instants), in the economy's time zone."""
        zone = await self.shared.zone()
        local = at.astimezone(zone).date()
        first = local.replace(day=1)
        following = date(first.year + first.month // 12, first.month % 12 + 1, 1)
        return (
            first,
            datetime.combine(first, datetime.min.time(), zone),
            datetime.combine(following, datetime.min.time(), zone),
        )

    async def current(self) -> tuple[BingoCard, datetime, datetime]:
        now = utc_now(self.clock)
        first, start, end = await self._month(now)
        async with self.database.session() as session:
            card = await session.get(BingoCard, first)
        if card is None:
            cells = draw(await self._sources().bingo_cells(year=first.year), first)
            if not cells:
                raise NoBingo("Not enough titles of different kinds for a bingo card.")
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(
                    insert(BingoCard)
                    .values(month=first, cells=cells, created_at=now)
                    .on_conflict_do_nothing()
                )
            async with self.database.session() as session:
                card = await session.get(BingoCard, first)
        assert card is not None
        return card, start, end

    @staticmethod
    def _size(card: BingoCard) -> int:
        return 4 if len(card.cells) == 16 else 3

    async def _award(self, card: BingoCard, ticks: Mapping[UUID, Mapping[str, BingoTick]]) -> int:
        """Each member's lines and full card not told yet: told once each (the rows' keys)."""
        now = utc_now(self.clock)
        keys = [cell["key"] for cell in card.cells]
        month = card.month.isoformat()
        told = 0
        async with self.database.unit_of_work() as uow:
            for user, found in ticks.items():
                ticked = {i for i, key in enumerate(keys) if key in found}
                done = [name for name, squares in lines(self._size(card)) if set(squares) <= ticked]
                if len(ticked) == len(keys):
                    done.append(CARD)
                for name in done:
                    inserted = await uow.session.execute(
                        insert(BingoDone)
                        .values(month=card.month, user_id=user, line=name, at=now)
                        .on_conflict_do_nothing()
                        .returning(BingoDone.line)
                    )
                    if inserted.first() is None or self.shared.events is None:
                        continue
                    if name == CARD:
                        event, payload = BINGO_CARD, {"month": month, "squares": len(keys)}
                    else:
                        count = len([d for d in done if d != CARD])
                        event, payload = BINGO_LINE, {"month": month, "line": name, "lines": count}
                    await self.shared.events.publish(
                        uow.session,
                        event,
                        payload,
                        occurred_at=now,
                        subject=SubjectRef("user", str(user)),
                        source="games",
                        dedup_key=f"{event}:{month}:{name}:{user}",
                    )
                    told += 1
        return told

    async def view(self, user: UUID) -> dict[str, Any]:
        if not self._open():
            raise GameClosed("The bingo is switched off.")
        card, start, end = await self.current()
        keys = [cell["key"] for cell in card.cells]
        found = (await self._sources().bingo_ticks(keys, start, end, user=user)).get(user, {})
        await self._award(card, {user: found} if found else {})
        size = self._size(card)
        ticked = {i for i, key in enumerate(keys) if key in found}
        async with self.database.session() as session:
            players, cards = (
                await session.execute(
                    select(
                        func.count(func.distinct(BingoDone.user_id)),
                        func.count().filter(BingoDone.line == CARD),
                    ).where(BingoDone.month == card.month)
                )
            ).one()
        drawn = lines(size)
        return {
            "month": card.month.isoformat(),
            "ends_at": end.isoformat(),
            "size": size,
            "cells": [
                {
                    "key": cell["key"],
                    "group": cell["group"],
                    "by": (
                        {
                            "id": str(tick.object_id) if tick.object_id else None,
                            "title": tick.title,
                            "image_id": str(tick.image_id) if tick.image_id else None,
                            "at": tick.at.isoformat(),
                        }
                        if (tick := found.get(cell["key"]))
                        else None
                    ),
                }
                for cell in card.cells
            ],
            "lines": [
                {"key": name, "cells": list(squares), "done": set(squares) <= ticked}
                for name, squares in drawn
            ],
            "squares": len(ticked),
            "done_lines": sum(1 for _, squares in drawn if set(squares) <= ticked),
            "card": len(ticked) == len(keys),
            "players": int(players or 0),
            "cards": int(cards or 0),
        }

    async def check(self) -> int:
        """Every half hour: who completed a line or the card since."""
        if not self._open():
            return 0
        try:
            card, start, end = await self.current()
        except NoBingo:
            return 0
        keys = [cell["key"] for cell in card.cells]
        return await self._award(card, await self._sources().bingo_ticks(keys, start, end))
