"""HTTP API of the shell module (contracts/shell-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.shell.api.router import router


def routers() -> list[APIRouter]:
    return [router]
