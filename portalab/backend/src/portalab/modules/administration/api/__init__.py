"""HTTP API of the administration module (contracts/config-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.administration.api.backups import router as backups
from portalab.modules.administration.api.routes import router


def routers() -> list[APIRouter]:
    return [router, backups]
