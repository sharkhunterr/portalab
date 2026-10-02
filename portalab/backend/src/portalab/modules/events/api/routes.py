"""Events API (T022, T028): own history, subject history, admin diagnostics, quarantine, replay."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.authorization import require
from portalab.core.authz_port import Authorizer, Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, NotFound, Unavailable
from portalab.modules.events.history.query import HistoryItem
from portalab.modules.events.models import Delivery, Event
from portalab.modules.events.module import EventsModule

router = APIRouter(prefix="/api/v1", tags=["events"])
SUBJECT_READ_PERMISSIONS = {"user": "users.read"}  # other subject types register as their modules land
FULL_VIEW_PERMISSION = "security.manage"


def events_module(request: Request) -> EventsModule:
    module = getattr(request.app.state, "events_module", None)
    if not isinstance(module, EventsModule):
        raise Unavailable("Events are not available.", code="events.unavailable")
    return module


Module = Annotated[EventsModule, Depends(events_module)]


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class ReplayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    projection: str = Field(min_length=1, max_length=128)
    from_occurred_at: datetime | None = None
    to_occurred_at: datetime | None = None
    confirmation: str | None = Field(default=None, max_length=128)


def _history(items: list[HistoryItem], next_cursor: str | None) -> dict[str, Any]:
    return {
        "items": [
            {
                "event_id": str(i.event_id),
                "type": i.type,
                "occurred_at": i.occurred_at.isoformat(),
                "source": i.source_system,
                "actor_kind": i.actor_kind,
                "subject_type": i.subject_type,
                "subject_id": i.subject_id,
                "payload": i.payload,
            }
            for i in items
        ],
        "next_cursor": next_cursor,
    }


@router.get("/me/history")
async def my_history(
    module: Module,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    principal: Principal = require("users.self.manage"),
) -> dict[str, Any]:
    assert principal.user_id is not None
    items, next_cursor = await module.history.for_user(
        principal, principal.user_id, cursor=cursor, limit=limit
    )
    return _history(items, next_cursor)


@router.get("/subjects/{subject_type}/{subject_id}/history")
async def subject_history(
    request: Request,
    module: Module,
    subject_type: Annotated[str, Path(max_length=64)],
    subject_id: Annotated[str, Path(max_length=128)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    principal: Principal = require("users.self.manage"),
) -> dict[str, Any]:
    permission = SUBJECT_READ_PERMISSIONS.get(subject_type)
    if permission is None:
        raise NotFound()
    authorizer: Authorizer = request.app.state.authorizer
    if not await authorizer.is_allowed(principal, permission, ResourceRef(subject_type, subject_id)):
        raise Forbidden()
    try:
        items, next_cursor = await module.history.for_subject(
            principal, subject_type, subject_id, cursor=cursor, limit=limit
        )
    except ValueError as exc:
        raise NotFound() from exc
    return _history(items, next_cursor)


@router.get("/admin/events")
async def admin_events(
    request: Request,
    module: Module,
    type_prefix: Annotated[str | None, Query(alias="type", max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_seq: int | None = None,
    principal: Principal = require("events.manage"),
) -> dict[str, Any]:
    statement = select(Event).order_by(Event.seq.desc()).limit(limit)
    if type_prefix:
        statement = statement.where(Event.type.startswith(type_prefix, autoescape=True))
    if before_seq:
        statement = statement.where(Event.seq < before_seq)
    async with module.database.session() as session:
        rows = list((await session.execute(statement)).scalars())
    authorizer: Authorizer = request.app.state.authorizer
    full = await authorizer.is_allowed(principal, FULL_VIEW_PERMISSION)
    return {
        "items": [
            {
                "seq": r.seq,
                "event_id": str(r.event_id),
                "type": r.type,
                "version": r.type_version,
                "occurred_at": r.occurred_at.isoformat(),
                "received_at": r.received_at.isoformat(),
                "source": r.source_system,
                "actor_kind": r.actor_kind,
                "actor_user_id": str(r.actor_user_id) if full and r.actor_user_id else None,
                "subject_type": r.subject_type,
                "subject_id": r.subject_id if full else None,
                "payload": r.payload if full else {"redacted": True, "keys": sorted(r.payload)},
            }
            for r in rows
        ]
    }


@router.get("/admin/events/deliveries")
async def admin_deliveries(
    module: Module,
    status_filter: Annotated[
        Literal["pending", "succeeded", "failed", "dead"] | None, Query(alias="status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    principal: Principal = require("events.manage"),
) -> dict[str, Any]:
    statement = select(Delivery).order_by(Delivery.updated_at.desc()).limit(limit)
    if status_filter:
        statement = statement.where(Delivery.status == status_filter)
    async with module.database.session() as session:
        rows = list((await session.execute(statement)).scalars())
    return {
        "items": [
            {
                "consumer": r.consumer,
                "event_id": str(r.event_id),
                "status": r.status,
                "attempts": r.attempts,
                "last_error": r.last_error,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/admin/events/quarantine")
async def admin_quarantine(
    module: Module,
    status_filter: Annotated[Literal["open", "released", "discarded"] | None, Query(alias="status")] = "open",
    principal: Principal = require("events.manage"),
) -> dict[str, Any]:
    rows = await module.quarantine.list(status_filter)
    return {
        "items": [
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "reason": r.reason,
                "detail": r.detail,
                "received_at": r.received_at.isoformat(),
                "status": r.status,
                "source": r.source_system,
            }
            for r in rows
        ]
    }


@router.post("/admin/events/quarantine/{item_id}/{action}", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_quarantine(
    item_id: UUID,
    action: Literal["release", "discard"],
    module: Module,
    principal: Principal = require("events.manage"),
) -> Response:
    await module.quarantine.resolve(principal, item_id, action, module.publisher)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/admin/replay",
    status_code=status.HTTP_202_ACCEPTED,
    responses={409: {"description": "authz.confirmation_required (carries `confirmation`)"}},
)
async def replay(
    body: ReplayIn, module: Module, principal: Principal = require("events.replay")
) -> dict[str, Any]:
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource = ResourceRef("projection", body.projection)
    payload = {
        "projection": body.projection,
        "from": str(body.from_occurred_at),
        "to": str(body.to_occurred_at),
    }
    if body.confirmation is None:
        issued = await confirmations.issue(principal, "events.replay", resource, payload)
        raise ConfirmationRequired(
            "Replaying rebuilds this projection from history. Confirm to continue.",
            extensions={"confirmation": issued},
        )
    if not await confirmations.consume(body.confirmation, principal, "events.replay", resource, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
    run = await module.replay.rebuild(
        body.projection,
        actor=principal,
        from_occurred_at=body.from_occurred_at,
        to_occurred_at=body.to_occurred_at,
    )
    return {"run": str(run.id), "status": run.status, "processed": run.processed}
