"""Community HTTP API (contracts/community-contracts.md, slice A)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.community.api.events import router as events
    from portalab.modules.community.api.public import router as public

    return [public, events]
