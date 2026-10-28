"""Issue 265: what the games page shows around the games — each game's board (the week's, the month's or of
all time: each member's best score; the parties' wins; the challenges completed), what I played today and my
best this week, and the administrators' figures (games played, players)."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, distinct, func, select

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.games.common import Shared
from portalab.modules.games.models import ChallengeDone, GameSession, Party, PartyPlayer
from portalab.modules.games.settings import GAMES, PARTY_ONLY, ROUND_GAMES, SOLO_ONLY

PERIODS = ("week", "month", "all")
TOP = 10


class Boards:
    def __init__(self, database: Database, shared: Shared, *, clock: Clock | None = None) -> None:
        self.database = database
        self.shared = shared
        self.clock = clock

    async def _since(self, period: str) -> datetime | None:
        now = utc_now(self.clock)
        if period == "week":
            return (await self.shared.week(now))[1]
        if period == "month":
            zone = await self.shared.zone()
            local = now.astimezone(zone)
            return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return None

    async def board(self, user: UUID, game: str, period: str) -> dict[str, Any]:
        since = await self._since(period)
        async with self.database.session() as session:
            if game == "party":
                query = (
                    select(PartyPlayer.user_id, func.count())
                    .join(Party, Party.id == PartyPlayer.party_id)
                    .where(Party.status == "done", PartyPlayer.rank == 1)
                    .group_by(PartyPlayer.user_id)
                )
                if since is not None:
                    query = query.where(Party.updated_at >= since)
            elif game == "challenge":
                query = select(ChallengeDone.user_id, func.count()).group_by(ChallengeDone.user_id)
                if since is not None:
                    query = query.where(ChallengeDone.at >= since)
            else:
                query = (
                    select(GameSession.user_id, func.max(GameSession.score))
                    .where(GameSession.game == game, GameSession.status == "done")
                    .group_by(GameSession.user_id)
                )
                if since is not None:
                    query = query.where(GameSession.finished_at >= since)
            rows = sorted(
                ((u, int(v or 0)) for u, v in (await session.execute(query)).all()), key=lambda r: -r[1]
            )
        names = await self.shared.names([u for u, _ in rows[:TOP]] + [user])
        entries = [
            {"rank": at + 1, "name": names.get(u), "value": v, "me": u == user}
            for at, (u, v) in enumerate(rows)
        ]
        mine = next((e for e in entries if e["me"]), None)
        return {"game": game, "period": period, "entries": entries[:TOP], "me": mine}

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
