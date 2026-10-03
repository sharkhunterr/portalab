"""AI HTTP API (contracts/ai-contracts.md)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.ai.api.admin import router as admin
    from portalab.modules.ai.api.router import router as user

    return [user, admin]
