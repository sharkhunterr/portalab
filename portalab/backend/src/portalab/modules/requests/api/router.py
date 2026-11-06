"""Issue 363, #378: the kinds of titles asked of the team — what « Ask for a title » offers beside the films
and series. The requests themselves are the media's (``POST /media/requests``)."""

from typing import Any

from fastapi import APIRouter

from portalab.capabilities.media_core import default_media_types
from portalab.modules.requests.api.deps import Module, Reader

SCREEN = ("movie", "series")  # the request service's

router = APIRouter(prefix="/api/v1", tags=["requests"])


@router.get("/requests/options")
async def options(principal: Reader, module: Module) -> dict[str, Any]:
    """The kinds the team takes, and every kind it could (the whole titles the portal knows beside films
    and series — a plugin's too)."""
    known = [t.kind for t in default_media_types.all() if not t.parent_kinds and t.kind not in SCREEN]
    return {"kinds": module.team.kinds(), "known": known}
