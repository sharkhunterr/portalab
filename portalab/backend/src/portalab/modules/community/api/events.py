"""Community events API (T014): reads honour the audience tier; writes need ``community.events.manage``
(moderators/Admin) and are audited."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import ValidationFailed
from portalab.modules.community.api.public import Module
from portalab.modules.community.events.service import EventInput
from portalab.modules.community.models import CommunityEvent
from portalab.modules.community.permissions import EVENTS_MANAGE, READ

router = APIRouter(prefix="/api/v1", tags=["community"])
Reader = Annotated[Principal, require(READ)]
Manager = Annotated[Principal, require(EVENTS_MANAGE)]
MAX_WINDOW = timedelta(days=400)


class CommunityEventOut(BaseModel):
    id: UUID
    title: str
    description_md: str
    rendered_html: str
    starts_at: datetime
    ends_at: datetime | None
    all_day: bool
    reference_tz: str
    audience: str
    audience_roles: list[str]
    status: str
    version: int
    updated_at: datetime


def event_out(event: CommunityEvent) -> CommunityEventOut:
    return CommunityEventOut(
        id=event.id,
        title=event.title,
        description_md=event.description_md,
        rendered_html=event.rendered_html,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        all_day=event.all_day,
        reference_tz=event.reference_tz,
        audience=event.audience,
        audience_roles=list(event.audience_roles),
        status=event.status,
        version=event.version,
        updated_at=event.updated_at,
    )


@router.get("/community/events", response_model=list[CommunityEventOut])
async def list_events(
    principal: Reader, module: Module, start: datetime | None = None, end: datetime | None = None
) -> list[CommunityEventOut]:
    start = start or datetime.now(UTC) - timedelta(days=1)
    end = end or start + timedelta(days=90)
    if start.tzinfo is None or end.tzinfo is None or end <= start or end - start > MAX_WINDOW:
        raise ValidationFailed("Invalid time window.", code="community.invalid_window")
    return [event_out(e) for e in await module.events.between(principal, start, end)]


@router.get("/community/events/{event_id}", response_model=CommunityEventOut)
async def get_event(principal: Reader, event_id: UUID, module: Module) -> CommunityEventOut:
    return event_out(await module.events.get(principal, event_id))


@router.post("/community/events", response_model=CommunityEventOut, status_code=201)
async def create_event(principal: Manager, body: EventInput, module: Module) -> CommunityEventOut:
    return event_out(await module.events.create(principal, body))


@router.patch("/community/events/{event_id}", response_model=CommunityEventOut)
async def update_event(
    principal: Manager, event_id: UUID, body: EventInput, module: Module
) -> CommunityEventOut:
    return event_out(await module.events.update(principal, event_id, body))


@router.post("/community/events/{event_id}/cancel", response_model=CommunityEventOut)
async def cancel_event(principal: Manager, event_id: UUID, module: Module) -> CommunityEventOut:
    return event_out(await module.events.cancel(principal, event_id))
