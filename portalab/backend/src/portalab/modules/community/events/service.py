"""Community events (T014; owner decision 2026-10-01): dated happenings with a sanitized Markdown description
(011 renderer), start/end or all-day, a reference time zone and an audience tier — ``public``,
``community`` (any signed-in member) or ``roles``. Managers (``community.events.manage``) create, edit and
cancel them (audited, ``community.event_created|updated|cancelled`` emitted once per version). The 011
Calendar consumes them as ``CalendarSource(kind="community_event")``; reminders re-check ``item`` at fire
time, so a cancelled or no-longer-permitted event is never announced."""

from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.content import CalendarItem, CalendarSourceResult
from portalab.capabilities.content.render import render_markdown
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Authorizer, Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.community.models import CommunityEvent
from portalab.modules.community.permissions import EVENTS_MANAGE, READ

Audience = Literal["public", "community", "roles"]
KIND = "community_event"


class EventInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description_md: str = Field(default="", max_length=20_000)
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = False
    reference_tz: str = Field(default="UTC", max_length=64)
    audience: Audience = "community"
    audience_roles: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("reference_tz")
    @classmethod
    def _zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("unknown time zone") from error
        return value

    @field_validator("starts_at", "ends_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps carry a time zone offset")
        return value

    @model_validator(mode="after")
    def _coherent(self) -> "EventInput":
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("an event ends after it starts")
        if self.audience == "roles" and not [r for r in self.audience_roles if r.strip()]:
            raise ValueError("a role audience names at least one role")
        if self.audience != "roles":
            self.audience_roles = []
        return self


def _validate(data: EventInput) -> EventInput:
    try:
        return EventInput.model_validate(data.model_dump())
    except ValueError as error:
        raise ValidationFailed(str(error), code="community.invalid_event") from error


class CommunityEvents:
    kind = KIND
    label_key = "community:calendar.source"

    def __init__(
        self,
        database: Database,
        audit: AuditSink,
        events: EventPublisher,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.audit = audit
        self.events = events
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.clock = clock

    # --- audience ------------------------------------------------------------------------------------
    async def _roles(self, viewer: Principal) -> frozenset[str]:
        user = viewer.acting_for or viewer.user_id
        providers = self.capabilities.system_providers(ROLES_CAPABILITY)
        if user is None or not providers:
            return frozenset()
        return frozenset(await providers[0].provider.roles_of(user))

    async def may_see(self, viewer: Principal, event: CommunityEvent) -> bool:
        if not await self.authorizer.is_allowed(viewer, READ):
            return False
        if event.audience == "public" or await self.authorizer.is_allowed(viewer, EVENTS_MANAGE):
            return True
        if event.audience == "community":
            return viewer.is_authenticated
        return bool(await self._roles(viewer) & set(event.audience_roles))

    # --- reads ---------------------------------------------------------------------------------------
    async def between(self, viewer: Principal, start: datetime, end: datetime) -> list[CommunityEvent]:
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(CommunityEvent)
                        .where(
                            CommunityEvent.starts_at < end,
                            ((CommunityEvent.ends_at.is_(None)) & (CommunityEvent.starts_at >= start))
                            | (CommunityEvent.ends_at > start),
                        )
                        .order_by(CommunityEvent.starts_at, CommunityEvent.id)
                        .limit(500)
                    )
                ).scalars()
            )
        return [row for row in rows if await self.may_see(viewer, row)]

    async def get(self, viewer: Principal, event_id: UUID) -> CommunityEvent:
        async with self.database.session() as session:
            row = await session.get(CommunityEvent, event_id)
        if row is None or not await self.may_see(viewer, row):
            raise NotFound("No such event.", code="community.event_not_found")
        return row

    # --- writes --------------------------------------------------------------------------------------
    async def _record(
        self, session: AsyncSession, actor: Principal, action: str, event: CommunityEvent
    ) -> None:
        published = await self.events.publish(
            session,
            f"community.{action}",
            {"event": str(event.id), "version": event.version},
            occurred_at=utc_now(self.clock),
            actor=actor,
            subject=SubjectRef("community_event", str(event.id)),
            dedup_key=f"community.{action}:{event.id}:{event.version}",
        )
        await self.audit.record(
            session,
            AuditRecord(
                action=f"community.{action}",
                actor=actor,
                resource=ResourceRef(KIND, str(event.id)),
                decision="allow",
                context={"version": event.version, "audience": event.audience, "status": event.status},
                sensitive=True,
                event_id=getattr(published, "event_id", None),
            ),
        )

    async def create(self, actor: Principal, data: EventInput) -> CommunityEvent:
        data = _validate(data)
        now = utc_now(self.clock)
        event = CommunityEvent(
            title=data.title.strip(),
            description_md=data.description_md,
            rendered_html=render_markdown(data.description_md).html,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            all_day=data.all_day,
            reference_tz=data.reference_tz,
            audience=data.audience,
            audience_roles=data.audience_roles,
            organizer_id=actor.acting_for or actor.user_id,
            status="scheduled",
            version=1,
            created_at=now,
            updated_at=now,
        )
        async with self.database.unit_of_work() as uow:
            uow.session.add(event)
            await uow.session.flush()
            await self._record(uow.session, actor, "event_created", event)
        return event

    async def update(self, actor: Principal, event_id: UUID, data: EventInput) -> CommunityEvent:
        data = _validate(data)
        async with self.database.unit_of_work() as uow:
            event = await uow.session.get(CommunityEvent, event_id, with_for_update=True)
            if event is None:
                raise NotFound("No such event.", code="community.event_not_found")
            if event.status == "cancelled":
                raise Conflict("A cancelled event cannot be edited.", code="community.event_cancelled")
            event.title = data.title.strip()
            event.description_md = data.description_md
            event.rendered_html = render_markdown(data.description_md).html
            event.starts_at, event.ends_at, event.all_day = data.starts_at, data.ends_at, data.all_day
            event.reference_tz = data.reference_tz
            event.audience, event.audience_roles = data.audience, data.audience_roles
            event.version += 1
            event.updated_at = utc_now(self.clock)
            await self._record(uow.session, actor, "event_updated", event)
        return event

    async def cancel(self, actor: Principal, event_id: UUID) -> CommunityEvent:
        async with self.database.unit_of_work() as uow:
            event = await uow.session.get(CommunityEvent, event_id, with_for_update=True)
            if event is None:
                raise NotFound("No such event.", code="community.event_not_found")
            if event.status == "cancelled":
                return event
            event.status = "cancelled"
            event.version += 1
            event.updated_at = utc_now(self.clock)
            await self._record(uow.session, actor, "event_cancelled", event)
        return event

    # --- 011 calendar source -------------------------------------------------------------------------
    def calendar_item(self, event: CommunityEvent) -> CalendarItem:
        local = event.starts_at.astimezone(ZoneInfo(event.reference_tz))
        return CalendarItem(
            source_kind=KIND,
            source_id=str(event.id),
            type="community_event",
            title=event.title,
            starts_at=None if event.all_day else event.starts_at,
            ends_at=None if event.all_day else event.ends_at,
            date=local.date() if event.all_day else None,
            all_day=event.all_day,
            reference_tz=event.reference_tz,
            status=event.status,
            url_ref=f"/community/events/{event.id}",
        )

    async def items(
        self, start: datetime, end: datetime, viewer: Principal, ctx: LocaleContext
    ) -> CalendarSourceResult:
        rows = await self.between(viewer, start, end)
        return CalendarSourceResult([self.calendar_item(r) for r in rows], "ok", utc_now(self.clock))

    async def item(self, source_id: str, viewer: Principal) -> CalendarItem | None:
        try:
            event_id = UUID(source_id)
        except ValueError:
            return None
        try:
            return self.calendar_item(await self.get(viewer, event_id))
        except NotFound:
            return None
