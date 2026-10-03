"""Campaigns HTTP API (contracts/campaigns-contracts.md)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.campaigns.api.admin import router as admin
    from portalab.modules.campaigns.api.public import router as public

    return [public, admin]
