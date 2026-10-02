"""HTTP API of the observability module (contracts/observability-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.observability.api.metrics import router as metrics_router
from portalab.modules.observability.api.routes import router as admin_router


def routers() -> list[APIRouter]:
    return [admin_router, metrics_router]
