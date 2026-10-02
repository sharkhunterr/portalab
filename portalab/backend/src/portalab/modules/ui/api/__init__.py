"""HTTP API of the UI module (contracts/ui-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.ui.api.router import router


def routers() -> list[APIRouter]:
    return [router]
