"""HTTP API of the authorization module (contracts/authz-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.authz.api.routes import router


def routers() -> list[APIRouter]:
    return [router]
