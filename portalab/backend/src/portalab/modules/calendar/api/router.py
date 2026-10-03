"""Calendar API: the federated view (items filtered at their sources, per-source states) and the user's
reminders."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.i18n import RESOLVER, LocaleContext
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.calendar.module import CalendarModule
from portalab.modules.calendar.permissions import CALENDAR_READ, SELF

router = APIRouter(prefix="/api/v1", tags=["calendar"])


def calendar_module(request: Request) -> CalendarModule:
    module = getattr(request.app.state, "calendar_module", None)
    if not isinstance(module, CalendarModule):
        raise Unavailable("The calendar is not available.", code="calendar.unavailable")
    return module


Module = Annotated[CalendarModule, Depends(calendar_module)]
Reader = Annotated[Principal, require(CALENDAR_READ)]
User = Annotated[Principal, require(SELF)]


class CalendarItemOut(BaseModel):
    source_kind: str
    source_id: str
    type: str
    title: str
    starts_at: datetime | None
    ends_at: datetime | None
    date: date | None
    all_day: bool
    reference_tz: str | None
    status: str
    url_ref: str | None


class CalendarOut(BaseModel):
    items: list[CalendarItemOut]
    source_states: dict[str, str]
    sources: dict[str, str]
    lead_options: list[int]
    as_of: datetime


class CalendarReminderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_kind: str = Field(max_length=40)
    source_id: str = Field(max_length=200)
    lead_minutes: int = Field(ge=1, le=60 * 24 * 30)


class CalendarReminderOut(BaseModel):
    id: UUID
    source_kind: str
    source_id: str
    lead_minutes: int
    remind_at: datetime
    status: str
    title: str


async def _ctx(module: CalendarModule, principal: Principal) -> LocaleContext:
    try:
        providers = module.capabilities.system_providers(RESOLVER)
        user = principal.acting_for or principal.user_id
        if providers and user is not None:
            ctx = await providers[0].provider.for_user(user)
            if isinstance(ctx, LocaleContext):
                return ctx
    except Exception:  # noqa: S110 — the default locale context is fine for a calendar view
        pass
    return LocaleContext()


@router.get("/calendar", response_model=CalendarOut)
async def calendar(
    principal: Reader,
    module: Module,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
    types: Annotated[list[str] | None, Query(max_length=10)] = None,
) -> CalendarOut:
    view = await module.aggregator.view(
        principal, start, end, await _ctx(module, principal), types=set(types or []) or None
    )
    return CalendarOut(
        items=[
            CalendarItemOut(**{k: getattr(i, k) for k in CalendarItemOut.model_fields}) for i in view.items
        ],
        source_states=view.source_states,
        sources={s.kind: s.label_key for s in module.sources.all() if s.kind in view.source_states},
        lead_options=list(module.config.reminder_lead_options),
        as_of=view.as_of,
    )


def _reminder(r: object) -> CalendarReminderOut:
    return CalendarReminderOut(**{k: getattr(r, k) for k in CalendarReminderOut.model_fields})


@router.get("/me/calendar/reminders", response_model=list[CalendarReminderOut])
async def reminders(principal: User, module: Module) -> list[CalendarReminderOut]:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return [_reminder(r) for r in await module.reminders.mine(user)]


@router.post(
    "/me/calendar/reminders", response_model=CalendarReminderOut, status_code=status.HTTP_201_CREATED
)
async def add_reminder(principal: User, body: CalendarReminderIn, module: Module) -> CalendarReminderOut:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return _reminder(await module.reminders.create(user, body.source_kind, body.source_id, body.lead_minutes))


@router.delete("/me/calendar/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_reminder(principal: User, reminder_id: UUID, module: Module) -> Response:
    user = principal.acting_for or principal.user_id
    assert user is not None
    await module.reminders.remove(user, reminder_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
