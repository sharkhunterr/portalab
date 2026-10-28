"""Issue 265: the games page — its games, their boards; a game alone (question after question, the memory),
the day's title to find, the week's challenge; the parties played together, joined by their code. Every
answer is checked and timed by the server; the images and sounds of a question are asked of it as it runs."""

import re
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Path, Query, Request, Response, status
from pydantic import BaseModel, Field

from portalab.modules.games.api.deps import Module, Player, me
from portalab.modules.games.boards import PERIODS
from portalab.modules.games.settings import GAMES

router = APIRouter(prefix="/api/v1", tags=["games"])
Code = Annotated[str, Path(min_length=4, max_length=6, pattern=r"^[A-Za-z]+$")]
NO_STORE = {"Cache-Control": "no-store"}


class AnswerIn(BaseModel):
    choice: str | None = Field(default=None, max_length=16)
    order: list[Annotated[str, Field(max_length=16)]] | None = Field(default=None, max_length=10)

    def given(self) -> Any:
        return self.order if self.order is not None else self.choice


class FlipIn(BaseModel):
    position: int = Field(ge=0, le=60)


class GuessIn(BaseModel):
    guess: str = Field(min_length=1, max_length=60)


class PartyIn(BaseModel):
    game: str = Field(max_length=24)
    rounds: int | None = Field(default=None, ge=1, le=30)
    seconds: int | None = Field(default=None, ge=5, le=180)
    host_plays: bool = True


@router.get("/games")
async def games(principal: Player, module: Module) -> dict[str, Any]:
    """The games open, what I played this week, the day's title (found or not) and my parties."""
    user = me(principal)
    return await module.boards.hub(user) | {"parties": await module.parties.mine(user)}


@router.get("/games/leaderboard")
async def leaderboard(
    principal: Player,
    module: Module,
    game: Annotated[str, Query(max_length=24)],
    period: Annotated[Literal["week", "month", "all"], Query()] = "week",
) -> dict[str, Any]:
    """A game's board: each member's best score (``party``: the parties won; ``challenge``: the weeks)."""
    if game not in (*GAMES, "party") or period not in PERIODS:
        return {"game": game, "period": period, "entries": [], "me": None}
    return await module.boards.board(me(principal), game, period)


@router.post("/games/memory/sessions", status_code=status.HTTP_201_CREATED)
async def start_memory(principal: Player, module: Module) -> dict[str, Any]:
    """A memory: my own cards (or the library's posters) laid face down by the server."""
    return await module.solo.memory(me(principal))


@router.post("/games/{game}/sessions", status_code=status.HTTP_201_CREATED)
async def start(
    principal: Player, module: Module, game: Annotated[str, Path(max_length=24)]
) -> dict[str, Any]:
    """A game alone, question after question (``poster``, ``casting``, ``synopsis``, ``higher_lower``,
    ``timeline``, ``blindtest``, ``memories``)."""
    return await module.solo.start(me(principal), game)


@router.get("/games/sessions/{session_id}")
async def session(principal: Player, module: Module, session_id: UUID) -> dict[str, Any]:
    return await module.solo.view(me(principal), session_id)


@router.post("/games/sessions/{session_id}/answer")
async def answer(principal: Player, module: Module, session_id: UUID, body: AnswerIn) -> dict[str, Any]:
    """My answer to the question asked (a choice, or an order): its result and the right answer."""
    return await module.solo.answer(me(principal), session_id, body.given())


@router.post("/games/sessions/{session_id}/next")
async def next_question(principal: Player, module: Module, session_id: UUID) -> dict[str, Any]:
    return await module.solo.next(me(principal), session_id)


@router.post("/games/sessions/{session_id}/flip")
async def flip(principal: Player, module: Module, session_id: UUID, body: FlipIn) -> dict[str, Any]:
    """The memory: a card turned over (two not matching turn back at the next)."""
    return await module.solo.flip(me(principal), session_id, body.position)


@router.get("/games/sessions/{session_id}/image", response_class=Response)
async def session_image(principal: Player, module: Module, session_id: UUID) -> Response:
    """The question's poster, as blurred as its time says (sharp once answered)."""
    data = await module.solo.media(me(principal), session_id, "image")
    return Response(data, media_type="image/jpeg", headers=NO_STORE)


def _audio(data: bytes, request: Request) -> Response:
    """A theme tune, in the byte ranges a player asks for (Safari plays nothing without them)."""
    size = len(data)
    headers = {**NO_STORE, "Accept-Ranges": "bytes"}
    asked = re.fullmatch(r"bytes=(\d*)-(\d*)", request.headers.get("range", "").strip())
    if asked and size and any(asked.groups()):
        first, last = asked.groups()
        start = int(first) if first else max(0, size - int(last))
        end = min(int(last), size - 1) if first and last else size - 1
        if start <= end:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
            return Response(data[start : end + 1], status_code=206, media_type="audio/mpeg", headers=headers)
    return Response(data, media_type="audio/mpeg", headers=headers)


@router.get("/games/sessions/{session_id}/audio", response_class=Response)
async def session_audio(principal: Player, module: Module, session_id: UUID, request: Request) -> Response:
    return _audio(await module.solo.media(me(principal), session_id, "audio"), request)


@router.get("/games/cinemot")
async def cinemot(principal: Player, module: Module) -> dict[str, Any]:
    """The day's title to find: its letters' pattern, its hints, my guesses so far."""
    return await module.cinemot.today(me(principal))


@router.post("/games/cinemot/guesses")
async def cinemot_guess(principal: Player, module: Module, body: GuessIn) -> dict[str, Any]:
    return await module.cinemot.guess(me(principal), body.guess)


@router.get("/games/challenge")
async def challenge(principal: Player, module: Module) -> dict[str, Any]:
    """The week's challenges — a game to play, a film to watch through, a book and an audiobook to take
    some way: the title, the target, where I am (what my services and the portal tell)."""
    return await module.challenges.view(me(principal))


@router.get("/games/parties")
async def my_parties(principal: Player, module: Module) -> dict[str, Any]:
    return {"items": await module.parties.mine(me(principal))}


@router.post("/games/parties", status_code=status.HTTP_201_CREATED)
async def open_party(principal: Player, module: Module, body: PartyIn) -> dict[str, Any]:
    """A party on a game, its code to share; its host plays too unless they only run it (a screen)."""
    return await module.parties.create(
        me(principal), body.game, rounds=body.rounds, seconds=body.seconds, host_plays=body.host_plays
    )


@router.get("/games/parties/{code}")
async def party(principal: Player, module: Module, code: Code) -> dict[str, Any]:
    return await module.parties.view(me(principal), code)


@router.post("/games/parties/{code}/join")
async def join(principal: Player, module: Module, code: Code) -> dict[str, Any]:
    return await module.parties.join(me(principal), code)


@router.post("/games/parties/{code}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave(principal: Player, module: Module, code: Code) -> None:
    await module.parties.leave(me(principal), code)


@router.post("/games/parties/{code}/start")
async def start_party(principal: Player, module: Module, code: Code) -> dict[str, Any]:
    return await module.parties.start(me(principal), code)


@router.post("/games/parties/{code}/answer")
async def party_answer(principal: Player, module: Module, code: Code, body: AnswerIn) -> dict[str, Any]:
    return await module.parties.answer(me(principal), code, body.given())


@router.post("/games/parties/{code}/next")
async def party_next(principal: Player, module: Module, code: Code) -> dict[str, Any]:
    return await module.parties.next(me(principal), code)


@router.get("/games/parties/{code}/image", response_class=Response)
async def party_image(principal: Player, module: Module, code: Code) -> Response:
    data = await module.parties.media(me(principal), code, "image")
    return Response(data, media_type="image/jpeg", headers=NO_STORE)


@router.get("/games/parties/{code}/audio", response_class=Response)
async def party_audio(principal: Player, module: Module, code: Code, request: Request) -> Response:
    return _audio(await module.parties.media(me(principal), code, "audio"), request)
