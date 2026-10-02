"""HTTP API of the events module (contracts/events-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.events.api.routes import router


def routers() -> list[APIRouter]:
    return [router]
