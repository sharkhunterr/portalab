"""Issue 265: the games, for the administrators — their configuration (``games.config``, written like any
setting), the figures of what was played, and drawing the week's challenge again."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from portalab.modules.games.api.deps import Manager, Module
from portalab.modules.games.settings import (
    CHALLENGE_KINDS,
    GAMES,
    KEY,
    PARTY_ONLY,
    ROUND_GAMES,
    SOLO_ONLY,
)

router = APIRouter(prefix="/api/v1", tags=["games"])


@router.get("/admin/games")
async def games_admin(principal: Manager, module: Module) -> dict[str, Any]:
    """The games' configuration in force, the games there are, and what was played (7 and 30 days)."""
    return {
        "key": KEY,
        "config": module.config.model_dump(mode="json")
        | {
            "rounds": {g: module.config.round(g).model_dump() for g in ROUND_GAMES},
            "challenge": module.config.challenge.model_dump()
            | {"kinds": {k: module.config.challenge.of(k).model_dump() for k in CHALLENGE_KINDS}},
        },
        "games": list(GAMES),
        "challenge_kinds": list(CHALLENGE_KINDS),
        "round_games": list(ROUND_GAMES),
        "solo_only": list(SOLO_ONLY),
        "party_only": list(PARTY_ONLY),
        "figures": await module.boards.figures(),
    }


@router.post("/admin/games/challenge/redraw")
async def redraw(
    principal: Manager,
    module: Module,
    kind: Annotated[Literal["game", "movie", "book", "audiobook"] | None, Query()] = None,
) -> dict[str, Any]:
    """This week's challenges drawn again — one kind or all (a title pinned stays)."""
    return await module.challenges.redraw(kind)
