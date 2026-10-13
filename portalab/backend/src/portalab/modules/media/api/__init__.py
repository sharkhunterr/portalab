"""HTTP API of the media module (contracts/media-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.media.api.books import router as books_router
from portalab.modules.media.api.people import router as people_router
from portalab.modules.media.api.player import router as player_router
from portalab.modules.media.api.router import router


def routers() -> list[APIRouter]:
    return [player_router, books_router, people_router, router]
