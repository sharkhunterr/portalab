"""HTTP API of the statistics module (contracts/statistics-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.statistics.api.router import router


def routers() -> list[APIRouter]:
    return [router]
