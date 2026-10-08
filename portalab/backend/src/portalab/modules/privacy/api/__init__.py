"""HTTP API of the privacy module (contracts/privacy-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.privacy.api.routes import router
from portalab.modules.privacy.api.terms import router as terms_router


def routers() -> list[APIRouter]:
    return [router, terms_router]
