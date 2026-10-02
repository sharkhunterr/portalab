"""HTTP API of the connectors module (contracts/connector-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.connectors.api.services import router as services_router
from portalab.modules.connectors.api.sync import router as sync_router


def routers() -> list[APIRouter]:
    return [services_router, sync_router]
