"""Issue 265: the games played together — a party opened by its host on a game, joined with its code (four
letters) from any phone, the same questions for every player at the same time: the server keeps the time,
takes each answer once, tells the round once everyone answered or its time is up, then goes on after a few
seconds (or when the host says). The host may only run it (a television, a computer: the party's screen)
without playing. Every change is told live to the players (``games.party``: refetch), the pages also
looking now and then. Once over, each player's rank among how many goes to the reward rules
(``games.played``, ``mode`` party)."""

import random
import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from portalab.capabilities.media_core import GAME_SOURCES, SeenWork
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden
from portalab.core.live import publish_live
from portalab.core.time import Clock, utc_now
from portalab.modules.games.common import GameNotFound, Shared
from portalab.modules.games.models import OPEN, Party, PartyPlayer
from portalab.modules.games.pool import NoTitles, Pool
from portalab.modules.games.rounds import GRACE, make, public, worth
from portalab.modules.games.settings import ROUND_GAMES, SOLO_ONLY
from portalab.modules.games.solo import NotNow, blur_step

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I nor O: never mistaken for 1 or 0
TOPIC = "games.party"
IDLE = timedelta(hours=3)


class PartyFull(Conflict):
    default_code = "games.party_full"
    default_title = "The party is full"


class NotHost(Forbidden):
    default_code = "games.not_host"
    default_title = "Only the party's host may do that"


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Parties:
    def __init__(self, database: Database, pool: Pool, shared: Shared, *, clock: Clock | None = None) -> None:
        self.database = database
        self.pool = pool
        self.shared = shared
        self.clock = clock
        self.rng: random.Random = secrets.SystemRandom()

    # --- reading -----------------------------------------------------------------------------------------
    async def _load(self, session: Any, code: str, *, lock: bool = False) -> tuple[Party, list[PartyPlayer]]:
        query = (
            select(Party)
            .where(Party.code == code.upper().strip())
            .order_by(Party.status.in_(OPEN).desc(), Party.created_at.desc())
            .limit(1)
        )
        party = (await session.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
        if party is None:
            raise GameNotFound("No party with this code.")
        players = list(
            (
                await session.execute(
                    select(PartyPlayer)
                    .where(PartyPlayer.party_id == party.id)
                    .order_by(PartyPlayer.joined_at)
                )
            ).scalars()
        )
        return party, players

    @staticmethod
    def _member(party: Party, players: list[PartyPlayer], user: UUID) -> None:
        if party.host_id != user and not any(p.user_id == user for p in players):
            raise GameNotFound("No party with this code.")

    async def view(self, user: UUID, code: str) -> dict[str, Any]:
        now = utc_now(self.clock)
        async with self.database.session() as session:
            party, players = await self._load(session, code)
        self._member(party, players, user)
        if party.status == "playing" and self._due(party, players, now):
            async with self.database.unit_of_work() as uow:
                party, players = await self._load(uow.session, code, lock=True)
                if self._due(party, players, now):
                    await self._advance(uow.session, party, players, now)
        return await self._view(party, players, user, now)

    async def mine(self, user: UUID) -> list[dict[str, Any]]:
        """The open parties I host or play in."""
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Party)
                    .outerjoin(PartyPlayer, PartyPlayer.party_id == Party.id)
                    .where(Party.status.in_(OPEN), (Party.host_id == user) | (PartyPlayer.user_id == user))
                    .distinct()
                    .order_by(Party.created_at.desc())
                )
            ).scalars()
            return [
                {"code": p.code, "game": p.game, "status": p.status, "host": p.host_id == user} for p in rows
            ]

    async def _view(
        self, party: Party, players: list[PartyPlayer], user: UUID, now: datetime
    ) -> dict[str, Any]:
        names = await self.shared.names([party.host_id, *(p.user_id for p in players)])
        state = party.state
        at = state.get("at", 0)
        phase = state.get("phase")
        round_key = str(at)
        out: dict[str, Any] = {
            "code": party.code,
            "game": party.game,
            "status": party.status,
            "version": party.version,
            "host": names.get(party.host_id),
            "is_host": party.host_id == user,
            "playing": any(p.user_id == user for p in players),
            "settings": party.settings,
            "now": now.isoformat(),
            "players": [
                {
                    "id": str(p.user_id),
                    "name": names.get(p.user_id),
                    "score": p.score,
                    "rank": p.rank,
                    "answered": round_key in p.answers,
                    "points": p.answers.get(round_key, {}).get("points") if phase == "reveal" else None,
                    "me": p.user_id == user,
                }
                for p in sorted(players, key=lambda p: -p.score)
            ],
        }
        if party.status == "playing":
            question = state["questions"][at]
            started = _at(state["started"])
            out |= {
                "round": at + 1,
                "rounds": len(state["questions"]),
                "phase": phase,
                "started": state["started"],
                "deadline": (started + timedelta(seconds=party.settings["seconds"])).isoformat(),
                "question": public(question) if now >= started else None,  # the countdown: not yet
            }
            mine = next((p.answers.get(round_key) for p in players if p.user_id == user), None)
            if phase == "reveal":
                out["reveal"] = {
                    "answer": question["answer"],
                    "reveal": question["reveal"],
                    "mine": mine,
                    "next_at": (
                        _at(state["revealed"]) + timedelta(seconds=self.shared.config().party.reveal_seconds)
                    ).isoformat(),
                }
            else:
                out["given"] = mine.get("given") if mine else None
        elif party.status == "done":
            out["last"] = state.get("last")
        return out

    # --- the round's clock -------------------------------------------------------------------------------
    def _due(self, party: Party, players: list[PartyPlayer], now: datetime) -> bool:
        state = party.state
        if party.status != "playing":
            return False
        if state["phase"] == "question":
            deadline = _at(state["started"]) + timedelta(seconds=party.settings["seconds"] + GRACE)
            answered = all(str(state["at"]) in p.answers for p in players) and bool(players)
            return now >= deadline or answered
        revealed = _at(state["revealed"]) + timedelta(seconds=self.shared.config().party.reveal_seconds)
        return now >= revealed

    async def _advance(self, session: Any, party: Party, players: list[PartyPlayer], now: datetime) -> None:
        state = dict(party.state)
        if state["phase"] == "question":
            state["phase"] = "reveal"
            state["revealed"] = now.isoformat()
        elif state["at"] + 1 >= len(state["questions"]):
            await self._finish(session, party, players, now)
            return
        else:
            state["at"] += 1
            state["phase"] = "question"
            state["started"] = now.isoformat()
        party.state = state
        await self._changed(session, party, players, now)

    async def _finish(self, session: Any, party: Party, players: list[PartyPlayer], now: datetime) -> None:
        state = party.state
        question = state["questions"][state["at"]]
        rounds = len(state["questions"])
        ordered = sorted(players, key=lambda p: -p.score)
        for player in ordered:
            player.rank = 1 + sum(1 for other in ordered if other.score > player.score)
        party.status = "done"
        party.state = {"last": {"reveal": question["reveal"]}, "rounds": rounds}
        for player in ordered:
            await self.shared.played(
                session,
                player.user_id,
                key=f"party:{party.id}:{player.user_id}",
                game=party.game,
                mode="party",
                score=player.score,
                correct=sum(1 for a in player.answers.values() if a.get("correct")),
                rounds=rounds,
                won=player.rank == 1 and len(ordered) >= 2,
                rank=int(player.rank or 1),
                players=len(ordered),
                at=now,
            )
        await self._changed(session, party, players, now)

    async def _changed(self, session: Any, party: Party, players: list[PartyPlayer], now: datetime) -> None:
        party.version += 1
        party.updated_at = now
        for user in {party.host_id, *(p.user_id for p in players)}:
            await publish_live(
                session,
                topic=TOPIC,
                payload={"code": party.code, "version": party.version},
                audience_user_id=user,
                clock=self.clock,
            )

    # --- acting ------------------------------------------------------------------------------------------
    async def create(
        self,
        user: UUID,
        game: str,
        *,
        rounds: int | None = None,
        seconds: int | None = None,
        host_plays: bool = True,
    ) -> dict[str, Any]:
        if game not in ROUND_GAMES or game in SOLO_ONLY:
            raise GameNotFound("No such game to play together.")
        config = self.shared.open(game)
        if not config.party.enabled:
            raise Forbidden("Parties are switched off.", code="games.parties_off")
        settings = config.round(game)
        now = utc_now(self.clock)
        chosen = {
            "rounds": max(1, min(rounds or settings.rounds, 30)),
            "seconds": max(5, min(seconds or settings.seconds, 180)),
            "choices": settings.choices,
            "host_plays": host_plays,
        }
        async with self.database.unit_of_work() as uow:
            # a host runs one party at a time: an older one still open closes
            await uow.session.execute(
                update(Party)
                .where(Party.host_id == user, Party.status.in_(OPEN))
                .values(status="closed", updated_at=now)
            )
        for _ in range(12):
            code = "".join(self.rng.choice(ALPHABET) for _ in range(4))
            party = Party(
                code=code,
                host_id=user,
                game=game,
                status="lobby",
                settings=chosen,
                state={},
                version=1,
                created_at=now,
                updated_at=now,
            )
            try:
                async with self.database.unit_of_work() as uow:
                    uow.session.add(party)
                    await uow.session.flush()
                    if host_plays:
                        uow.session.add(
                            PartyPlayer(party_id=party.id, user_id=user, answers={}, joined_at=now)
                        )
            except IntegrityError:
                continue
            return await self.view(user, code)
        raise Conflict("No free party code; try again.", code="games.no_code")

    async def join(self, user: UUID, code: str) -> dict[str, Any]:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            party, players = await self._load(uow.session, code, lock=True)
            if party.status not in OPEN:
                raise GameNotFound("This party is over.")
            if not any(p.user_id == user for p in players):
                if len(players) >= self.shared.config().party.max_players:
                    raise PartyFull("The party is full.")
                player = PartyPlayer(party_id=party.id, user_id=user, answers={}, joined_at=now)
                uow.session.add(player)
                players.append(player)
                await self._changed(uow.session, party, players, now)
        return await self.view(user, code)

    async def leave(self, user: UUID, code: str) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            party, players = await self._load(uow.session, code, lock=True)
            if party.host_id == user:
                party.status = "closed" if party.status in OPEN else party.status
                await self._changed(uow.session, party, players, now)
                return
            for player in players:
                if player.user_id == user and party.status in OPEN:
                    await uow.session.delete(player)
                    await self._changed(uow.session, party, [p for p in players if p is not player], now)

    async def _players(self, players: list[PartyPlayer]) -> dict[UUID, tuple[str, list[SeenWork]]]:
        """« Who watched it? »: the players who agreed, with what they watched."""
        sources = self.shared.capabilities.system_providers(GAME_SOURCES)
        names = await self.shared.names(p.user_id for p in players)
        out: dict[UUID, tuple[str, list[SeenWork]]] = {}
        for player in players:
            if sources and await self.shared.shares(player.user_id):
                seen = list(await sources[0].provider.seen(player.user_id, limit=400))
                out[player.user_id] = (names[player.user_id], seen)
        return out

    async def start(self, user: UUID, code: str) -> dict[str, Any]:
        now = utc_now(self.clock)
        async with self.database.session() as session:
            party, players = await self._load(session, code)
        if party.host_id != user:
            raise NotHost("Only the host starts the party.")
        if party.status != "lobby":
            raise NotNow("The party has started already.")
        if not players:
            raise NotNow("Nobody plays yet.")
        config = self.shared.open(party.game)
        settings = config.round(party.game).model_copy(
            update={"rounds": party.settings["rounds"], "choices": party.settings["choices"]}
        )
        items = await self.pool.items(config)
        extra: dict[str, Any] = {}
        if party.game == "blindtest":
            series = [i for i in items if i.kind == "series"]
            self.rng.shuffle(series)
            extra["themed"] = await self.pool.with_themes(series, settings.rounds)
        if party.game == "whowatched":
            extra["players"] = await self._players(players)
            if len(extra["players"]) < 2:
                raise NoTitles("At least two players must agree to « who watched it? » (their settings).")
        questions = make(party.game, items, settings, self.rng, **extra)
        countdown = timedelta(seconds=config.party.countdown_seconds)
        async with self.database.unit_of_work() as uow:
            party, players = await self._load(uow.session, code, lock=True)
            if party.status != "lobby":
                raise NotNow("The party has started already.")
            party.status = "playing"
            party.state = {
                "questions": questions,
                "at": 0,
                "phase": "question",
                "started": (now + countdown).isoformat(),
            }
            await self._changed(uow.session, party, players, now)
        return await self.view(user, code)

    async def answer(self, user: UUID, code: str, given: Any) -> dict[str, Any]:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            party, players = await self._load(uow.session, code, lock=True)
            player = next((p for p in players if p.user_id == user), None)
            state = party.state
            if player is None or party.status != "playing" or state.get("phase") != "question":
                raise NotNow("No question to answer now.")
            key = str(state["at"])
            started = _at(state["started"])
            if key in player.answers or now < started:
                raise NotNow("Answered already, or not started yet.")
            question = state["questions"][state["at"]]
            right, points = worth(question, given, (now - started).total_seconds(), party.settings["seconds"])
            player.answers = {**player.answers, key: {"given": given, "correct": right, "points": points}}
            player.score += points
            if self._due(party, players, now):
                await self._advance(uow.session, party, players, now)
            else:
                await self._changed(uow.session, party, players, now)
        return await self.view(user, code)

    async def next(self, user: UUID, code: str) -> dict[str, Any]:
        """The host moves on: the round told now, or the next question."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            party, players = await self._load(uow.session, code, lock=True)
            if party.host_id != user:
                raise NotHost("Only the host moves the party on.")
            if party.status != "playing":
                raise NotNow("The party is not being played.")
            await self._advance(uow.session, party, players, now)
        return await self.view(user, code)

    async def media(self, user: UUID, code: str, what: str) -> bytes:
        now = utc_now(self.clock)
        async with self.database.session() as session:
            party, players = await self._load(session, code)
        self._member(party, players, user)
        state = party.state
        if party.status != "playing" or now < _at(state["started"]):
            raise NotNow("Nothing to show yet.")
        media = state["questions"][state["at"]].get("media") or {}
        if what == "image" and media.get("poster"):
            step = blur_step(
                _at(state["started"]), now, party.settings["seconds"], state["phase"] == "reveal"
            )
            return await self.pool.blurred(media["poster"], step)
        if what == "audio" and media.get("theme"):
            found = await self.pool.theme(UUID(media["theme"]))
            if found:
                return found
        raise GameNotFound("Nothing to show or hear.")

    async def sweep(self) -> int:
        """Parties left open three hours without a move close."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(
                update(Party)
                .where(Party.status.in_(OPEN), Party.updated_at < now - IDLE)
                .values(status="closed", updated_at=now)
            )
        return int(getattr(result, "rowcount", 0) or 0)
