"""HTTP API of the dashboard module (contracts/dashboard-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.dashboard.api.router import router


def routers() -> list[APIRouter]:
    return [router]
