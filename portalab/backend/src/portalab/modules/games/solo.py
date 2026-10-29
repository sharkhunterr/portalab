"""Issue 265: the games a member plays alone — question after question (each made on the server with its
answer: the page is told only the choices, and the result once it answered), the time measured by the server;
the memory (its faces laid on the server, turned one at a time). Once a game is over, only each round's
result is kept, and ``games.played`` says what it was worth to the reward rules."""

import random
import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.media_core import CARD_FACES, GAME_SOURCES
from portalab.core.db import Database
from portalab.core.errors import Conflict
from portalab.core.time import Clock, utc_now
from portalab.modules.games.common import GameNotFound, Shared
from portalab.modules.games.models import GameSession
from portalab.modules.games.pool import BLUR, NoTitles, Pool
from portalab.modules.games.rounds import make, public, worth
from portalab.modules.games.settings import PARTY_ONLY, ROUND_GAMES, GamesConfig

SUDDEN = ("higher_lower",)  # played until the first mistake


class NotNow(Conflict):
    default_code = "games.not_now"
    default_title = "Not at this point of the game"


class DailyLimit(Conflict):
    default_code = "games.daily_limit"
    default_title = "No more games of this one today"


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def blur_step(started: datetime, now: datetime, seconds: int, revealed: bool) -> int:
    """How sharp a poster is: a step each fifth of the round, sharp only once answered."""
    if revealed:
        return len(BLUR) - 1
    elapsed = (now - started).total_seconds()
    return max(0, min(len(BLUR) - 2, int(elapsed / max(1.0, seconds / (len(BLUR) - 1)))))


class Solo:
    def __init__(self, database: Database, pool: Pool, shared: Shared, *, clock: Clock | None = None) -> None:
        self.database = database
        self.pool = pool
        self.shared = shared
        self.clock = clock
        self.rng: random.Random = secrets.SystemRandom()

    # --- question after question -------------------------------------------------------------------------
    async def start(self, user: UUID, game: str) -> dict[str, Any]:
        if game not in ROUND_GAMES or game in PARTY_ONLY:
            raise GameNotFound("No such game to play alone.")
        config = self.shared.open(game)
        await self._may_start(user, game, config)
        settings = config.round(game)
        items = await self.pool.items(config)
        extra: dict[str, Any] = {}
        if game == "blindtest":
            series = [i for i in items if i.kind == "series"]
            self.rng.shuffle(series)
            extra["themed"] = await self.pool.with_themes(series, settings.rounds)
        if game == "memories":
            sources = self.shared.capabilities.system_providers(GAME_SOURCES)
            if not sources:
                raise NoTitles("No history to ask about.")
            extra["seen"] = list(await sources[0].provider.seen(user, limit=300))
            extra["unseen"] = [i for i in items if i.votes >= 1000]
        questions = make(game, items, settings, self.rng, **extra)
        now = utc_now(self.clock)
        row = GameSession(
            user_id=user,
            game=game,
            mode="solo",
            status="playing",
            state={
                "questions": questions,
                "at": 0,
                "phase": "question",
                "started": now.isoformat(),
                "seconds": settings.seconds,
                "results": [],
            },
            rounds=settings.rounds if game in SUDDEN else len(questions),
            started_at=now,
            updated_at=now,
        )
        async with self.database.unit_of_work() as uow:
            uow.session.add(row)
        return self._view(row, now)

    @staticmethod
    async def started_today(session: Any, user: UUID, since: datetime) -> dict[str, int]:
        """The games a member started alone since the day began, by game: each one started counts, finished
        or not — a game left to start it again is one played."""
        rows = await session.execute(
            select(GameSession.game, func.count())
            .where(GameSession.user_id == user, GameSession.mode == "solo", GameSession.started_at >= since)
            .group_by(GameSession.game)
        )
        return {game: int(count) for game, count in rows.all()}

    async def _may_start(self, user: UUID, game: str, config: GamesConfig) -> None:
        limit = config.per_day(game)
        if not limit:
            return
        since = await self.shared.day_start(utc_now(self.clock))
        async with self.database.session() as session:
            started = (await self.started_today(session, user, since)).get(game, 0)
        if started >= limit:
            raise DailyLimit(f"{limit} games of it a day: come back tomorrow.")

    async def _mine(self, session: Any, user: UUID, session_id: UUID, *, lock: bool = False) -> GameSession:
        query = select(GameSession).where(GameSession.id == session_id, GameSession.user_id == user)
        row = (await session.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
        if not isinstance(row, GameSession):
            raise GameNotFound("No such game.")
        return row

    async def view(self, user: UUID, session_id: UUID) -> dict[str, Any]:
        async with self.database.session() as session:
            row = await self._mine(session, user, session_id)
        return self._view(row, utc_now(self.clock))

    def _view(self, row: GameSession, now: datetime) -> dict[str, Any]:
        state = row.state
        out: dict[str, Any] = {
            "id": str(row.id),
            "game": row.game,
            "mode": row.mode,
            "status": row.status,
            "score": row.score,
            "correct": row.correct,
            "rounds": row.rounds,
            "results": [{"correct": r["correct"], "points": r["points"]} for r in state.get("results", [])],
            "now": now.isoformat(),
        }
        if row.game == "memory":
            return out | self._board(row)
        if row.status == "done":
            out["last"] = state.get("last")
            return out
        question = state["questions"][state["at"]]
        started = _at(state["started"])
        out |= {
            "round": state["at"] + 1,
            "phase": state["phase"],
            "seconds": state["seconds"],
            "started": state["started"],
            "deadline": (started + timedelta(seconds=state["seconds"])).isoformat(),
            "question": public(question),
        }
        if state["phase"] == "reveal":
            out["result"] = state["results"][-1] | {
                "answer": question["answer"],
                "reveal": question["reveal"],
            }
        return out

    async def answer(self, user: UUID, session_id: UUID, given: Any) -> dict[str, Any]:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await self._mine(uow.session, user, session_id, lock=True)
            state = dict(row.state)
            if row.status != "playing" or state.get("phase") != "question" or row.game == "memory":
                raise NotNow("This question is answered already.")
            question = state["questions"][state["at"]]
            elapsed = (now - _at(state["started"])).total_seconds()
            right, points = worth(question, given, elapsed, state["seconds"])
            state["results"] = [*state["results"], {"correct": right, "points": points, "given": given}]
            state["phase"] = "reveal"
            row.state = state
            row.score += points
            row.correct += int(right)
            row.updated_at = now
            view = self._view(row, now)
        return view

    async def next(self, user: UUID, session_id: UUID) -> dict[str, Any]:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await self._mine(uow.session, user, session_id, lock=True)
            state = dict(row.state)
            if row.status != "playing" or state.get("phase") != "reveal":
                raise NotNow("Answer the question first.")
            last = state["results"][-1]
            over = state["at"] + 1 >= len(state["questions"]) or (row.game in SUDDEN and not last["correct"])
            if over:
                question = state["questions"][state["at"]]
                row.status = "done"
                row.finished_at = now
                if row.game in SUDDEN:
                    row.rounds = len(state["results"])
                row.state = {
                    "results": [{"correct": r["correct"], "points": r["points"]} for r in state["results"]],
                    "last": {"reveal": question["reveal"], "correct": last["correct"]},
                }
                won = row.correct >= 10 if row.game in SUDDEN else row.correct * 2 >= max(1, row.rounds)
                await self.shared.played(
                    uow.session,
                    user,
                    key=str(row.id),
                    game=row.game,
                    mode="solo",
                    score=row.score,
                    correct=row.correct,
                    rounds=row.rounds,
                    won=won,
                    at=now,
                )
            else:
                state["at"] += 1
                state["phase"] = "question"
                state["started"] = now.isoformat()
                row.state = state
            row.updated_at = now
            view = self._view(row, now)
        return view

    async def media(self, user: UUID, session_id: UUID, what: str) -> bytes:
        """The current question's poster (blurred as its time runs) or theme music."""
        async with self.database.session() as session:
            row = await self._mine(session, user, session_id)
        state = row.state
        if row.status != "playing":
            raise NotNow("The game is over.")
        question = state["questions"][state["at"]]
        media = question.get("media") or {}
        if what == "image" and media.get("poster"):
            step = blur_step(
                _at(state["started"]), utc_now(self.clock), state["seconds"], state["phase"] == "reveal"
            )
            return await self.pool.blurred(media["poster"], step)
        if what == "audio" and media.get("theme"):
            found = await self.pool.theme(UUID(media["theme"]))
            if found:
                return found
        raise GameNotFound("Nothing to show or hear.")

    # --- the memory --------------------------------------------------------------------------------------
    async def memory(self, user: UUID) -> dict[str, Any]:
        config = self.shared.open("memory")
        await self._may_start(user, "memory", config)
        pairs = config.memory.pairs
        faces: list[dict[str, Any]] = []
        if config.memory.own_cards:
            cards = self.shared.capabilities.system_providers(CARD_FACES)
            if cards:
                faces = [
                    {"key": f"card:{c['id']}", "card": dict(c)}
                    for c in await cards[0].provider.faces(user, pairs)
                ]
        if len(faces) < pairs:
            posters = [i for i in await self.pool.items(config) if i.poster]
            self.rng.shuffle(posters)
            faces += [
                {"key": f"poster:{i.id}", "poster": i.poster, "title": i.title}
                for i in posters[: pairs - len(faces)]
            ]
        if len(faces) < pairs:
            raise NoTitles("Not enough cards or posters for the memory.")
        board = faces + faces
        self.rng.shuffle(board)
        now = utc_now(self.clock)
        row = GameSession(
            user_id=user,
            game="memory",
            mode="solo",
            status="playing",
            state={"faces": board, "matched": [], "open": [], "moves": 0},
            rounds=pairs,
            started_at=now,
            updated_at=now,
        )
        async with self.database.unit_of_work() as uow:
            uow.session.add(row)
        return self._view(row, now)

    def _board(self, row: GameSession) -> dict[str, Any]:
        state = row.state
        faces = state.get("faces", [])
        shown = set(state.get("matched", [])) | set(state.get("open", []))
        done = row.status == "done"
        return {
            "moves": state.get("moves", 0),
            "pairs": row.rounds,
            "board": [
                {
                    "state": "matched"
                    if at in state.get("matched", [])
                    else "open"
                    if at in shown
                    else "hidden",
                    "face": face if (at in shown or done) else None,
                }
                for at, face in enumerate(faces)
            ],
        }

    async def flip(self, user: UUID, session_id: UUID, position: int) -> dict[str, Any]:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await self._mine(uow.session, user, session_id, lock=True)
            state = dict(row.state)
            faces = state.get("faces", [])
            if row.game != "memory" or row.status != "playing" or not 0 <= position < len(faces):
                raise NotNow("Nothing to turn over there.")
            matched, opened = list(state["matched"]), list(state["open"])
            if len(opened) == 2:  # the two last turned over did not match: face down again
                opened = []
            if position in matched or position in opened:
                return self._view(row, now)
            opened.append(position)
            if len(opened) == 2:
                state["moves"] += 1
                a, b = opened
                if faces[a]["key"] == faces[b]["key"]:
                    matched += [a, b]
                    opened = []
            state["matched"], state["open"] = matched, opened
            row.state = state
            row.updated_at = now
            if len(matched) == len(faces):
                pairs = len(faces) // 2
                row.status = "done"
                row.finished_at = now
                row.correct = pairs
                row.score = max(100, 1000 - 50 * (state["moves"] - pairs))
                await self.shared.played(
                    uow.session,
                    user,
                    key=str(row.id),
                    game="memory",
                    mode="solo",
                    score=row.score,
                    correct=pairs,
                    rounds=pairs,
                    won=state["moves"] <= pairs * 2,
                    at=now,
                )
            view = self._view(row, now)
        return view
