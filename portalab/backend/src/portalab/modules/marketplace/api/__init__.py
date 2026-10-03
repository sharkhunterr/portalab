"""Marketplace HTTP API (contracts/marketplace-contracts.md)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.marketplace.api.admin import router as admin
    from portalab.modules.marketplace.api.projects import router as projects

    return [projects, admin]
