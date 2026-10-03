"""HTTP API of the wiki module."""

from fastapi import APIRouter

from portalab.modules.wiki.api.router import router


def routers() -> list[APIRouter]:
    return [router]
