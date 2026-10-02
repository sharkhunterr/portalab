"""HTTP API of the i18n module (contracts/i18n-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.i18n.api.router import router


def routers() -> list[APIRouter]:
    return [router]
