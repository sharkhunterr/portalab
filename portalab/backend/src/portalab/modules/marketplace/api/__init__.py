"""Marketplace HTTP API (contracts/marketplace-contracts.md)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.marketplace.api.admin import router as admin
    from portalab.modules.marketplace.api.catalog import router as catalog
    from portalab.modules.marketplace.api.catalog_admin import router as catalog_admin
    from portalab.modules.marketplace.api.projects import router as projects
    from portalab.modules.marketplace.api.requests import router as requests

    return [projects, admin, catalog, catalog_admin, requests]
