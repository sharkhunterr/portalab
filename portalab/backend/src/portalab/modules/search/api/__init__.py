"""HTTP API of the search module (contracts/search-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.search.api.router import router


def routers() -> list[APIRouter]:
    return [router]
