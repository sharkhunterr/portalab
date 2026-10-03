"""HTTP API of the support module (contracts/support-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.support.api.incidents import router


def routers() -> list[APIRouter]:
    return [router]
