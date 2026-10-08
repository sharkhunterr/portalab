"""HTTP API of the media module (contracts/media-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.media.api.player import router as player_router
from portalab.modules.media.api.router import router


def routers() -> list[APIRouter]:
    return [player_router, router]
