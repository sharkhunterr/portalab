"""HTTP API of the visuals module (specs/028-visual-packs/contracts/api-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.visuals.api.routes import admin, members


def routers() -> list[APIRouter]:
    return [members, admin]
