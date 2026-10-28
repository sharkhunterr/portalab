"""Issue 265: the day's title to find — a film or a series of the library, the same for every member that
day, guessed letter by letter in a few tries (each letter told right, in the title elsewhere, or absent). Its
kind, year and genres are given; the title is the server's until the game is over."""

import random
import re
import secrets
import unicodedata
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.ids import new_id
from portalab.core.time import Clock, utc_now
from portalab.modules.games.common import Shared
from portalab.modules.games.models import GameSession, Puzzle
from portalab.modules.games.pool import NoTitles, Pool
from portalab.modules.games.solo import NotNow

GAME = "cinemot"


def word_of(title: str) -> str | None:
    """A title as letters to find: capitals without accents, its words kept apart — none with figures or
    signs that cannot be typed."""
    plain = unicodedata.normalize("NFKD", title)
    plain = "".join(c for c in plain if not unicodedata.combining(c)).upper()
    plain = re.sub(r"['\u2019\-:,.!?&]", " ", plain)
    words = plain.split()
    if not words or any(not w.isascii() or not w.isalpha() for w in words):
        return None
    return " ".join(words)


def marks(word: str, guess: str) -> str:
    """Per letter: ``c`` in its place, ``p`` in the word elsewhere, ``a`` absent (each letter of the word
    told once)."""
    out = ["a"] * len(guess)
    left: dict[str, int] = {}
    for at, (w, g) in enumerate(zip(word, guess, strict=True)):
        if w == g:
            out[at] = "c"
        else:
            left[w] = left.get(w, 0) + 1
    for at, g in enumerate(guess):
        if out[at] != "c" and left.get(g, 0) > 0:
            out[at] = "p"
            left[g] -= 1
    return "".join(out)


class Cinemot:
    def __init__(self, database: Database, pool: Pool, shared: Shared, *, clock: Clock | None = None) -> None:
        self.database = database
        self.pool = pool
        self.shared = shared
        self.clock = clock
        self.rng: random.Random = secrets.SystemRandom()

    async def puzzle(self, day: date) -> Puzzle:
        async with self.database.session() as session:
            found = await session.get(Puzzle, (GAME, day))
        if found is not None:
            return found
        config = self.shared.open(GAME)
        rules = config.cinemot
        fit = []
        for item in await self.pool.items(config):
            word = word_of(item.title)
            letters = len(word.replace(" ", "")) if word else 0
            if word and rules.min_letters <= letters <= rules.max_letters and len(word.split()) <= 4:
                fit.append((item, word))
        if not fit:
            raise NoTitles("No title fits the day's puzzle.")
        item, word = self.rng.choice(fit)
        payload = {
            "word": word,
            "title": item.title,
            "year": item.year,
            "kind": item.kind,
            "poster": item.poster,
            "genres": list(item.genres[:2]),
        }
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(Puzzle)
                .values(game=GAME, day=day, object_id=item.id, payload=payload)
                .on_conflict_do_nothing()
            )
        async with self.database.session() as session:
            stored = await session.get(Puzzle, (GAME, day))
        assert stored is not None
        return stored

    async def _mine(self, user: UUID) -> tuple[GameSession, Puzzle]:
        now = utc_now(self.clock)
        day = await self.shared.today(now)
        puzzle = await self.puzzle(day)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(GameSession)
                .values(
                    id=new_id(),
                    user_id=user,
                    game=GAME,
                    mode="daily",
                    day=day,
                    status="playing",
                    state={"guesses": []},
                    score=0,
                    correct=0,
                    rounds=self.shared.config().cinemot.tries,
                    started_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["user_id", "game", "day"], index_where=text("day IS NOT NULL")
                )
            )
        async with self.database.session() as session:
            row = (
                await session.execute(
                    select(GameSession).where(
                        GameSession.user_id == user, GameSession.game == GAME, GameSession.day == day
                    )
                )
            ).scalar_one()
        return row, puzzle

    @staticmethod
    def _view(row: GameSession, puzzle: Puzzle) -> dict[str, Any]:
        word = str(puzzle.payload["word"])
        out: dict[str, Any] = {
            "id": str(row.id),
            "day": puzzle.day.isoformat(),
            "pattern": [len(w) for w in word.split()],
            "hints": {k: puzzle.payload.get(k) for k in ("kind", "year", "genres")},
            "guesses": row.state.get("guesses", []),
            "tries": row.rounds,
            "status": row.status,
            "won": row.correct > 0,
            "score": row.score,
        }
        if row.status == "done":
            out["answer"] = {
                "title": puzzle.payload["title"],
                "year": puzzle.payload.get("year"),
                "poster": puzzle.payload.get("poster"),
                "id": str(puzzle.object_id),
                "word": word,
            }
        return out

    async def today(self, user: UUID) -> dict[str, Any]:
        self.shared.open(GAME)
        row, puzzle = await self._mine(user)
        return self._view(row, puzzle)

    async def guess(self, user: UUID, text: str) -> dict[str, Any]:
        self.shared.open(GAME)
        row, puzzle = await self._mine(user)
        word = str(puzzle.payload["word"]).replace(" ", "")
        letters = (word_of(text) or "").replace(" ", "")
        if len(letters) != len(word):
            raise ValidationFailed(f"The title has {len(word)} letters.", code="games.letters")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            current = (
                await uow.session.execute(
                    select(GameSession).where(GameSession.id == row.id).with_for_update()
                )
            ).scalar_one()
            guesses = list(current.state.get("guesses", []))
            if current.status != "playing" or len(guesses) >= current.rounds:
                raise NotNow("Today's title is over.")
            told = marks(word, letters)
            guesses.append({"letters": letters, "marks": told})
            current.state = {"guesses": guesses}
            current.updated_at = now
            solved = told == "c" * len(word)
            if solved or len(guesses) >= current.rounds:
                current.status = "done"
                current.finished_at = now
                current.correct = int(solved)
                current.score = (current.rounds - len(guesses) + 1) * 100 if solved else 0
                await self.shared.played(
                    uow.session,
                    user,
                    key=str(current.id),
                    game=GAME,
                    mode="daily",
                    score=current.score,
                    correct=current.correct,
                    rounds=len(guesses),
                    won=solved,
                    at=now,
                )
            view = self._view(current, puzzle)
        return view
