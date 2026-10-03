"""HTTP API of the news module."""

from fastapi import APIRouter

from portalab.modules.news.api.router import router


def routers() -> list[APIRouter]:
    return [router]
