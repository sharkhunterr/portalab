"""Gamification HTTP API (contracts/economy-contracts.md)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.gamification.api.admin import router as admin
    from portalab.modules.gamification.api.me import router as me
    from portalab.modules.gamification.api.tuning import router as tuning

    return [me, admin, tuning]
