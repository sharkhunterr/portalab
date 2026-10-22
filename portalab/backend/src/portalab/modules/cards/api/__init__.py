"""HTTP API of the cards (issue 229)."""

from fastapi import APIRouter

from portalab.modules.cards.api.router import router


def routers() -> list[APIRouter]:
    return [router]
