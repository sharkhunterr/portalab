"""HTTP API of the news module."""

from fastapi import APIRouter

from portalab.modules.news.api.router import router
from portalab.modules.news.api.sources import router as sources_router


def routers() -> list[APIRouter]:
    return [sources_router, router]
