"""Issue 265: the week's challenges — one per kind: a game of the library (RomM) to play some minutes, a film
to watch through, a book and an audiobook to take some way. Nothing to declare: what the services' history,
play sessions and the portal's player and reader tell. The administrators pin a title or draw another;
otherwise one is drawn at random on the week's first visit. Who completes one is told once
(``games.challenge_completed``, with its kind), when they look or every half hour."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.media_core import GAME_SOURCES, GameSources, PlayableGame
from portalab.core.db import Database
from portalab.core.errors import Unavailable
from portalab.core.event_port import SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.games.common import GameClosed, Shared
from portalab.modules.games.events import CHALLENGE
from portalab.modules.games.models import Challenge, ChallengeDone

GAME = "challenge"


class NoGames(Unavailable):
    default_code = "games.no_title"
    default_title = "No title in the library for a challenge"


def reached(kind: str, value: float, target: int) -> bool:
    """A game: ``target`` minutes played; anything else: ``target`` percent of the way."""
    return value >= target * 60 if kind == "game" else value * 100 >= target


class Challenges:
    def __init__(self, database: Database, shared: Shared, *, clock: Clock | None = None) -> None:
        self.database = database
        self.shared = shared
        self.clock = clock

    def _sources(self) -> GameSources:
        providers = self.shared.capabilities.system_providers(GAME_SOURCES)
        if not providers:
            raise NoGames("The library cannot be read.")
        return cast(GameSources, providers[0].provider)

    def _open(self) -> list[str]:
        if GAME not in self.shared.config().enabled_games():
            return []
        return self.shared.config().challenge.open()

    async def _draw(self, kind: str) -> PlayableGame:
        sources = self._sources()
        pinned = self.shared.config().challenge.of(kind).item
        if pinned:
            found: PlayableGame | None
            try:
                found = await sources.title(UUID(pinned))
            except ValueError:
                found = None
            if found is not None and found.kind == kind:
                return found
        titles = list(await sources.titles(kind, limit=12))
        with_image = [t for t in titles if t.image_id] or titles
        if not with_image:
            raise NoGames("No such title in the library.")
        return with_image[0]

    async def current(self, kind: str) -> tuple[Challenge, datetime, datetime]:
        now = utc_now(self.clock)
        monday, start, end = await self.shared.week(now)
        async with self.database.session() as session:
            found = await session.get(Challenge, (monday, kind))
        if found is None:
            chosen = await self._draw(kind)
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(
                    insert(Challenge)
                    .values(
                        week=monday,
                        kind=kind,
                        object_id=chosen.object_id,
                        title=chosen.title[:200],
                        platform=(chosen.platform or None) and str(chosen.platform)[:80],
                        image_id=chosen.image_id,
                        minutes=self.shared.config().challenge.of(kind).target,
                        created_at=now,
                    )
                    .on_conflict_do_nothing()
                )
            async with self.database.session() as session:
                found = await session.get(Challenge, (monday, kind))
        assert found is not None
        return found, start, end

    async def redraw(self, kind: str | None = None) -> dict[str, Any]:
        """The administrators draw this week's challenges again (one kind, or all; a title pinned stays)."""
        monday, _, _ = await self.shared.week(utc_now(self.clock))
        async with self.database.unit_of_work() as uow:
            query = delete(Challenge).where(Challenge.week == monday)
            await uow.session.execute(query.where(Challenge.kind == kind) if kind else query)
        return await self.view(None)

    async def _award(self, challenge: Challenge, progress: dict[UUID, float]) -> set[UUID]:
        now = utc_now(self.clock)
        done: set[UUID] = set()
        async with self.database.unit_of_work() as uow:
            for user, value in progress.items():
                if not reached(challenge.kind, value, challenge.minutes):
                    continue
                inserted = await uow.session.execute(
                    insert(ChallengeDone)
                    .values(week=challenge.week, kind=challenge.kind, user_id=user, at=now)
                    .on_conflict_do_nothing()
                    .returning(ChallengeDone.user_id)
                )
                if inserted.first() is not None and self.shared.events is not None:
                    week = challenge.week.isoformat()
                    await self.shared.events.publish(
                        uow.session,
                        CHALLENGE,
                        {"week": week, "kind": challenge.kind, "target": challenge.minutes},
                        occurred_at=now,
                        subject=SubjectRef("user", str(user)),
                        source="games",
                        dedup_key=f"{CHALLENGE}:{week}:{challenge.kind}:{user}",
                    )
                    done.add(user)
        return done

    async def _one(self, kind: str, user: UUID | None) -> dict[str, Any] | None:
        try:
            challenge, start, end = await self.current(kind)
        except NoGames:
            return None
        progress = dict(await self._sources().progress(kind, challenge.object_id, start))
        await self._award(challenge, progress)
        async with self.database.session() as session:
            finishers = await session.scalar(
                select(func.count())
                .select_from(ChallengeDone)
                .where(ChallengeDone.week == challenge.week, ChallengeDone.kind == kind)
            )
            mine = (
                await session.get(ChallengeDone, (challenge.week, kind, user)) if user is not None else None
            )
        value = progress.get(user, 0.0) if user is not None else 0.0
        return {
            "kind": kind,
            "week": challenge.week.isoformat(),
            "ends_at": end.isoformat(),
            "title": {
                "id": str(challenge.object_id),
                "title": challenge.title,
                "platform": challenge.platform,
                "image_id": str(challenge.image_id) if challenge.image_id else None,
            },
            "target": challenge.minutes,
            "unit": "minutes" if kind == "game" else "percent",
            "mine": round(value / 60, 1) if kind == "game" else round(min(1.0, value) * 100),
            "done": mine is not None,
            "finishers": int(finishers or 0),
        }

    async def view(self, user: UUID | None) -> dict[str, Any]:
        kinds = self._open()
        if not kinds:
            raise GameClosed("The challenges are switched off.")
        items = [found for kind in kinds if (found := await self._one(kind, user)) is not None]
        return {"items": items}

    async def check(self) -> int:
        """Every half hour: who completed one of this week's challenges since."""
        told = 0
        for kind in self._open():
            try:
                challenge, start, _ = await self.current(kind)
            except NoGames:
                continue
            progress = dict(await self._sources().progress(kind, challenge.object_id, start))
            told += len(await self._award(challenge, progress))
        return told
