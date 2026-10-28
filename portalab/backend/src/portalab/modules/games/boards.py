"""Issue 265: what the games page shows around the games — each game's board (the week's, the month's or of
all time: each member's best score; the parties' wins; the challenges completed), what I played today and my
best this week, and the administrators' figures (games played, players). When a week or a month is over,
the members placed on each board are told their place (``games.board_ranked``), once — for the reward
rules the administrators set (« first of the week on the cast », « on the podium of the month »)."""

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.db import Database
from portalab.core.event_port import SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.games.common import Shared
from portalab.modules.games.events import BOARD
from portalab.modules.games.models import ChallengeDone, GameSession, Party, PartyPlayer
from portalab.modules.games.settings import GAMES, PARTY_ONLY, ROUND_GAMES, SOLO_ONLY

PERIODS = ("week", "month", "all")
TOP = 10


class Boards:
    def __init__(self, database: Database, shared: Shared, *, clock: Clock | None = None) -> None:
        self.database = database
        self.shared = shared
        self.clock = clock
        self._told: set[tuple[str, date]] = set()  # the periods already told since the start

    async def _since(self, period: str) -> datetime | None:
        now = utc_now(self.clock)
        if period == "week":
            return (await self.shared.week(now))[1]
        if period == "month":
            zone = await self.shared.zone()
            local = now.astimezone(zone)
            return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return None

    @staticmethod
    async def _standings(
        session: AsyncSession, game: str, since: datetime | None, until: datetime | None = None
    ) -> list[tuple[UUID, int]]:
        """A board between two instants: each member's best score (parties won, challenges completed),
        the best first."""
        if game == "party":
            at: Any = Party.updated_at
            query = (
                select(PartyPlayer.user_id, func.count())
                .join(Party, Party.id == PartyPlayer.party_id)
                .where(Party.status == "done", PartyPlayer.rank == 1)
                .group_by(PartyPlayer.user_id)
            )
        elif game == "challenge":
            at = ChallengeDone.at
            query = select(ChallengeDone.user_id, func.count()).group_by(ChallengeDone.user_id)
        else:
            at = GameSession.finished_at
            query = (
                select(GameSession.user_id, func.max(GameSession.score))
                .where(GameSession.game == game, GameSession.status == "done")
                .group_by(GameSession.user_id)
            )
        if since is not None:
            query = query.where(at >= since)
        if until is not None:
            query = query.where(at < until)
        return sorted(
            ((u, int(v or 0)) for u, v in (await session.execute(query)).all()), key=lambda r: -r[1]
        )

    async def board(self, user: UUID, game: str, period: str) -> dict[str, Any]:
        since = await self._since(period)
        async with self.database.session() as session:
            rows = await self._standings(session, game, since)
        names = await self.shared.names([u for u, _ in rows[:TOP]] + [user])
        entries = [
            {"rank": at + 1, "name": names.get(u), "value": v, "me": u == user}
            for at, (u, v) in enumerate(rows)
        ]
        mine = next((e for e in entries if e["me"]), None)
        return {"game": game, "period": period, "entries": entries[:TOP], "me": mine}

    async def _closed(self) -> list[tuple[str, date, datetime, datetime]]:
        """The week and the month just over: (period, first day, start, end)."""
        now = utc_now(self.clock)
        zone = await self.shared.zone()
        monday, week_start, _ = await self.shared.week(now)
        local = now.astimezone(zone)
        first = local.date().replace(day=1)
        previous = (first - timedelta(days=1)).replace(day=1)
        return [
            ("week", monday - timedelta(days=7), week_start - timedelta(days=7), week_start),
            (
                "month",
                previous,
                datetime.combine(previous, time.min, zone),
                datetime.combine(first, time.min, zone),
            ),
        ]

    async def close(self) -> int:
        """Every hour: a week or a month over, each member placed on a board (a score above nothing) is told
        their place — once (the event's key), whatever the hour the job runs at."""
        config = self.shared.config()
        if not config.enabled or self.shared.events is None:
            return 0
        # each game played alone (its best scores), the parties won, the challenges completed
        boards = [g for g in config.enabled_games() if g in GAMES and g not in PARTY_ONLY]
        if config.party.enabled:
            boards.append("party")
        told = 0
        now = utc_now(self.clock)
        for period, first, start, end in await self._closed():
            if (period, first) in self._told:
                continue
            async with self.database.unit_of_work() as uow:
                for game in boards:
                    rows = [r for r in await self._standings(uow.session, game, start, end) if r[1] > 0]
                    for at, (user, value) in enumerate(rows[:TOP]):
                        payload = {
                            "game": game,
                            "period": period,
                            "start": first.isoformat(),
                            "rank": at + 1,
                            "value": value,
                            "players": len(rows),
                        }
                        result = await self.shared.events.publish(
                            uow.session,
                            BOARD,
                            payload,
                            occurred_at=now,
                            subject=SubjectRef("user", str(user)),
                            source="games",
                            dedup_key=f"{BOARD}:{game}:{period}:{first.isoformat()}:{user}",
                        )
                        told += 0 if result.duplicate else 1
            self._told.add((period, first))
        return told

    async def hub(self, user: UUID) -> dict[str, Any]:
        config = self.shared.config()
        now = utc_now(self.clock)
        today = await self.shared.today(now)
        week = (await self.shared.week(now))[1]
        async with self.database.session() as session:
            best: dict[str, int] = {
                game: int(score or 0)
                for game, score in (
                    await session.execute(
                        select(GameSession.game, func.max(GameSession.score))
                        .where(
                            GameSession.user_id == user,
                            GameSession.status == "done",
                            GameSession.finished_at >= week,
                        )
                        .group_by(GameSession.game)
                    )
                ).all()
            }
            daily = (
                await session.execute(
                    select(GameSession.status, GameSession.correct).where(
                        GameSession.user_id == user, GameSession.game == "cinemot", GameSession.day == today
                    )
                )
            ).first()
        games = []
        for game in config.enabled_games():
            entry: dict[str, Any] = {"key": game, "best_week": best.get(game)}
            if game in ROUND_GAMES:
                settings = config.round(game)
                entry |= {
                    "kind": "rounds",
                    "solo": game not in PARTY_ONLY,
                    "party": game not in SOLO_ONLY and config.party.enabled,
                    "rounds": settings.rounds,
                    "seconds": settings.seconds,
                }
            else:
                entry |= {"kind": game, "solo": True, "party": False}
            games.append(entry)
        return {
            "enabled": config.enabled,
            "games": games,
            "party": config.party.enabled,
            "cinemot": None if daily is None else {"status": daily[0], "won": bool(daily[1])},
        }

    async def figures(self) -> dict[str, Any]:
        """The administrators' figures: games played in the last 7 and 30 days, and by how many members."""
        now = utc_now(self.clock)
        week, month = now - timedelta(days=7), now - timedelta(days=30)
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        GameSession.game,
                        func.count().filter(GameSession.finished_at >= week),
                        func.count(),
                        func.count(distinct(GameSession.user_id)),
                    )
                    .where(GameSession.status == "done", GameSession.finished_at >= month)
                    .group_by(GameSession.game)
                )
            ).all()
            parties = (
                await session.execute(
                    select(Party.game, func.count(), func.count(distinct(PartyPlayer.user_id)))
                    .join(PartyPlayer, PartyPlayer.party_id == Party.id)
                    .where(and_(Party.status == "done", Party.updated_at >= month))
                    .group_by(Party.game)
                )
            ).all()
        solo = {g: {"week": w, "month": m, "players": p} for g, w, m, p in rows}
        together = {g: {"parties": n, "players": p} for g, n, p in parties}
        return {g: {"solo": solo.get(g), "party": together.get(g)} for g in GAMES}
