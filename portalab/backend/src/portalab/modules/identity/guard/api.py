"""The security blocks, for the holders of ``security.manage`` (spec 028 FR-040): listed with their reason and
time left, lifted one by one or all at once — in the database (every process follows within seconds)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.identity.guard.guard import IntrusionGuard
from portalab.modules.identity.guard.store import BlockStore

router = APIRouter(prefix="/api/v1", tags=["security"])
Manager = Annotated[Principal, require("security.manage")]


def _guard(request: Request) -> IntrusionGuard:
    guard: IntrusionGuard | None = request.app.state._state.get("intrusion_guard")
    if guard is None:
        raise Unavailable("The intrusion guard is not running.", code="security.guard_unavailable")
    return guard


def _store(request: Request) -> BlockStore | None:
    store: BlockStore | None = request.app.state._state.get("security_blocks")
    return store


@router.get("/admin/security/blocks")
async def blocks(_: Manager, request: Request) -> dict[str, Any]:
    guard, store = _guard(request), _store(request)
    if store is not None:
        guard.load(await store.active())
    return {"blocks": guard.blocks()}


class LiftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str | None = Field(default=None, max_length=200)  # none: every block
    id: UUID | None = None


@router.post("/admin/security/blocks/lift")
async def lift(principal: Manager, request: Request, body: LiftIn) -> dict[str, Any]:
    """One block (its ``id`` or its ``key``), or every block when neither is given."""
    guard, store = _guard(request), _store(request)
    lifted = 0
    if store is not None:
        by = str(principal.user_id)
        if body.id is not None:
            lifted = await store.lift(by=by, block=body.id)
        elif body.key:
            lifted = await store.lift(by=by, subject=body.key.split(":", 1)[-1])
        else:
            lifted = await store.lift(by=by)
        guard.load(await store.active())  # what was lifted leaves this process too
    local = guard.lift(body.key) if body.key else guard.lift() if body.id is None else 0
    return {"lifted": max(lifted, local)}
