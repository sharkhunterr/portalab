"""Plugins HTTP API (contracts/extensibility-contracts.md)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.plugins.api.admin import router as admin
    from portalab.modules.plugins.api.modules import router as modules
    from portalab.modules.plugins.api.runtime import router as runtime

    return [admin, modules, runtime]
