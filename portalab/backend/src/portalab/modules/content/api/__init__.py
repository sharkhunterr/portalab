"""HTTP API of the content helper module (contracts/content-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.content.api.router import router


def routers() -> list[APIRouter]:
    return [router]
