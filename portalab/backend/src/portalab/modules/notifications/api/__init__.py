"""HTTP API of the notifications module (contracts/notifications-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.notifications.api.router import router


def routers() -> list[APIRouter]:
    return [router]
