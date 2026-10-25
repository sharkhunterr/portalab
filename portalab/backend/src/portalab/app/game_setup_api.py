"""Issue 253 — the game setup's API: the setups Portalab ships (the LAN's), the portal's own as it stands, and
one applied (a shipped one, or one taken from another portal). Applying changes the play and the campaigns,
so it needs both administrations."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from portalab.app import game_setup
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, Unavailable, ValidationFailed

router = APIRouter(prefix="/api/v1", tags=["game-setup"])
Manager = Annotated[Principal, require("gamification.manage")]


def _platform(request: Request) -> Any:
    platform = getattr(request.app.state, "platform", None)
    if platform is None:
        raise Unavailable("The game setup is not available.", code="game.setup_unavailable")
    return platform


Platform = Annotated[Any, Depends(_platform)]


@router.get("/admin/game/presets")
async def presets(_: Manager) -> list[dict[str, Any]]:
    return [{"key": key, "counts": game_setup.counts(game_setup.preset(key))} for key in game_setup.PRESETS]


@router.get("/admin/game/setup")
async def current(_: Manager, platform: Platform) -> dict[str, Any]:
    return await game_setup.export(platform)


Part = Literal["settings", "curve", "rules", "achievements", "quests", "campaigns"]
PARTS: tuple[Part, ...] = ("settings", "curve", "rules", "achievements", "quests", "campaigns")


class ApplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: Literal["lan"] | None = None
    setup: dict[str, Any] | None = None
    parts: list[Part] = Field(default_factory=lambda: list(PARTS))


@router.post("/admin/game/setup")
async def apply(
    principal: Manager,
    _campaigns: Annotated[Principal, require("campaigns.manage")],
    body: ApplyIn,
    platform: Platform,
) -> dict[str, Any]:
    if (body.preset is None) == (body.setup is None):
        raise ValidationFailed("Give a preset or a setup.", code="game.setup_invalid")
    try:
        setup = game_setup.preset(body.preset) if body.preset else dict(body.setup or {})
    except KeyError as exc:
        raise NotFound("No such game setup.", code="game.preset_not_found") from exc
    try:
        return await game_setup.apply(platform, principal, setup, tuple(body.parts))
    except ValueError as exc:
        raise ValidationFailed(str(exc), code="game.setup_invalid") from exc
