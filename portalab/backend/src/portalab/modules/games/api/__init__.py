"""HTTP API of the games (issue 265)."""

from fastapi import APIRouter

from portalab.modules.games.api.admin import router as admin
from portalab.modules.games.api.router import router


def routers() -> list[APIRouter]:
    return [router, admin]
