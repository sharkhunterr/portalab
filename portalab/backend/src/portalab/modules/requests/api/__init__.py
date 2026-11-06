"""HTTP API of the requests (issue 363)."""

from fastapi import APIRouter

from portalab.modules.requests.api.admin import router as admin
from portalab.modules.requests.api.router import router


def routers() -> list[APIRouter]:
    return [router, admin]
