"""Automations HTTP API (contracts/automations-contracts.md)."""

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    from portalab.modules.automations.api.admin import router

    return [router]
