"""HTTP API of the privacy module (contracts/privacy-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.privacy.api.routes import router


def routers() -> list[APIRouter]:
    return [router]
