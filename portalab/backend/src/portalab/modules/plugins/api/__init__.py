"""Plugins HTTP API (contracts/extensibility-contracts.md)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.plugins.api.admin import router as admin
    from portalab.modules.plugins.api.confined import router as confined
    from portalab.modules.plugins.api.modules import router as modules
    from portalab.modules.plugins.api.runtime import router as runtime

    return [confined, admin, modules, runtime]  # confined first: /admin/plugins/runtime is not a key
