"""HTTP API of the identity module (contracts/identity-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.identity.api import admin, auth, lifecycle, profile


def routers() -> list[APIRouter]:
    return [auth.router, profile.router, lifecycle.router, admin.router]
