"""HTTP API of the household module (spec 032, contracts/household-api.md)."""

from fastapi import APIRouter

from portalab.modules.household.api import routes


def routers() -> list[APIRouter]:
    return [routes.router]
