"""HTTP API of the support module (contracts/support-contracts.md)."""

from fastapi import APIRouter

from portalab.modules.support.api.admin import router as admin_router
from portalab.modules.support.api.diagnosis import router as diagnosis_router
from portalab.modules.support.api.feedback import router as feedback_router
from portalab.modules.support.api.incidents import router
from portalab.modules.support.api.tickets import router as tickets_router


def routers() -> list[APIRouter]:
    return [router, tickets_router, feedback_router, diagnosis_router, admin_router]
