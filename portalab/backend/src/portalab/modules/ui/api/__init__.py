"""HTTP API of the UI module (contracts/ui-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.ui.api.router import router
from portalab.modules.ui.api.visuals import router as visuals_router


def routers() -> list[APIRouter]:
    return [router, visuals_router]
