"""HTTP API of the health module (contracts/health-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.health.api.health import router as health_router
from portalab.modules.health.api.maintenance import router as maintenance_router
from portalab.modules.health.api.operations import router as operations_router


def routers() -> list[APIRouter]:
    return [health_router, maintenance_router, operations_router]
