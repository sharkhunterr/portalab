"""Issue 363: the requests, for the administrators — the queue (the open and most wanted first, who wants
each), its figures, and moving a request on: accepted, in progress, refused (why), there (the library's
title). The module's configuration (``requests.config``) is written like any setting."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from portalab.capabilities.media_core import default_media_types
from portalab.modules.requests.api.deps import Manager, Module, me
from portalab.modules.requests.models import STATUSES
from portalab.modules.requests.settings import KEY

router = APIRouter(prefix="/api/v1", tags=["requests"])
Status = Literal["new", "accepted", "in_progress", "available", "refused", "cancelled"]


class DecisionIn(BaseModel):
    status: Literal["new", "accepted", "in_progress", "available", "refused"]
    reason: str | None = Field(default=None, max_length=500)  # why it is refused
    object_id: UUID | None = None  # the library's title, once there


@router.get("/admin/requests")
async def queue(
    principal: Manager,
    module: Module,
    status: Annotated[Status | None, Query()] = None,
    kind: Annotated[str | None, Query(max_length=40)] = None,
) -> dict[str, Any]:
    return {
        "key": KEY,
        "config": module.config.model_dump(mode="json"),
        # the kinds of titles the portal knows (a plugin's too), each a whole title (not a season, a track)
        "known_kinds": [t.kind for t in default_media_types.all() if not t.parent_kinds],
        "statuses": list(STATUSES),
        "figures": await module.requests.figures(),
        "requests": await module.requests.queue(status, kind),
    }


@router.post("/admin/requests/{request_id}/decision")
async def decide(principal: Manager, module: Module, request_id: UUID, body: DecisionIn) -> dict[str, Any]:
    return await module.requests.decide(
        me(principal), request_id, body.status, reason=body.reason, object_id=body.object_id
    )
