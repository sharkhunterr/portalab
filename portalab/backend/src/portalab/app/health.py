"""Liveness and readiness (research R14). Public, unauthenticated, no sensitive detail."""

from typing import Any

from fastapi import APIRouter, Request

from portalab.app.migrations import is_up_to_date
from portalab.app.security import public
from portalab.core.db import Database
from portalab.core.errors import Unavailable

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Process is alive")
@public
async def healthz() -> dict[str, Any]:
    return {"status": "ok"}


@router.get("/readyz", summary="Database reachable and migrations current")
@public
async def readyz(request: Request) -> dict[str, Any]:
    database: Database | None = getattr(request.app.state, "database", None)
    if database is None or not await database.ping():
        raise Unavailable("The database is not reachable.", code="not_ready.database")
    heads: set[str] = request.app.state.migration_heads
    if not await is_up_to_date(database, heads):
        raise Unavailable("Database migrations are not current.", code="not_ready.migrations")
    return {"status": "ready"}
