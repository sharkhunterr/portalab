"""HTTP API of the retro module (issue 419)."""

from fastapi import APIRouter

from portalab.modules.retro.api import routes


def routers() -> list[APIRouter]:
    return [routes.router]
