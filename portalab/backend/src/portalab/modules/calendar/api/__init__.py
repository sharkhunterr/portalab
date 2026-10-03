"""HTTP API of the calendar module."""

from fastapi import APIRouter

from portalab.modules.calendar.api.router import router


def routers() -> list[APIRouter]:
    return [router]
