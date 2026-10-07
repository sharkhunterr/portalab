"""Ticket integrations (T035, T039): search providers ``tickets`` (own tickets for users, all for staff) and
``feedback`` (staff), widgets ``support.my_tickets`` and ``support.queue`` (009), palette actions
``support.new_ticket`` / ``support.report_bug`` (008) and the 019 action types ``ticket.create`` /
``incident.create`` running as the automation's author under the same rules."""

import time
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select

from portalab.capabilities.automation_actions import ActionRegistry, ActionType
from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import ActionDef, FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.capabilities.support import TicketRequest
from portalab.core.authz_port import Principal
from portalab.core.errors import Forbidden
from portalab.core.time import Clock, utc_now
from portalab.modules.support.incidents.service import IncidentService
from portalab.modules.support.models import FeedbackItem, Ticket
from portalab.modules.support.permissions import INCIDENTS_MANAGE
from portalab.modules.support.tickets.service import TICKETS_CREATE, TICKETS_MANAGE, TicketService

OWNER = "module:support"
ACTIONS = (
    ActionDef(
        "support.new_ticket",
        "support:action.new_ticket",
        TICKETS_CREATE,
        route="/support/new",
        keywords=("ticket", "help", "support"),
    ),
    ActionDef(
        "support.report_bug",
        "support:action.report_bug",
        "feedback.submit",
        route="/feedback?form=bug_report",
        keywords=("bug", "report"),
    ),
)


class TicketSearchProvider:
    kind = "tickets"
    label_key = "search.kind.tickets"
    required_permission = TICKETS_CREATE

    def __init__(self, tickets: TicketService) -> None:
        self.tickets = tickets

    def facets(self) -> Sequence[FacetDef]:
        return (FacetDef("state", "search.facet.state"),)

    def _item(self, row: Ticket, query: ParsedQuery) -> SearchItem:
        return SearchItem(
            kind=self.kind,
            id=str(row.id),
            title=f"T-{row.number:06d} · {row.title}",
            url_ref=f"/support/tickets/{row.id}",
            snippet=snippet(row.description[:400] or row.title, query.terms),
            facets={"state": row.state},
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        user = self.tickets.user_of(principal)
        staff = await self.tickets.allowed(principal, TICKETS_MANAGE)
        if user is None or not query.text.strip():
            return ProviderResult()
        needle = f"%{query.text.strip()[:80]}%"
        stmt = select(Ticket).where(or_(Ticket.title.ilike(needle), Ticket.description.ilike(needle)))
        number = query.text.strip().lstrip("#").removeprefix("T-").lstrip("0")
        if number.isdigit():
            stmt = select(Ticket).where(or_(Ticket.number == int(number), Ticket.title.ilike(needle)))
        if not staff:
            stmt = stmt.where(Ticket.requester_id == user)  # scoped at the source
        offset = decode_cursor(cursor)
        async with self.tickets.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        stmt.order_by(Ticket.updated_at.desc()).offset(offset).limit(limit + 1)
                    )
                )
                .scalars()
                .all()
            )
        return ProviderResult(
            items=[self._item(r, query) for r in rows[:limit]],
            next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        out = []
        empty = ParsedQuery(text="", normalized="", terms=())
        for value in ids:
            try:
                view = await self.tickets.view(UUID(value), principal)
            except Exception:  # noqa: S112 — not visible: dropped silently
                continue
            out.append(self._item(view.ticket, empty))
        return out


class FeedbackSearchProvider:
    kind = "feedback"
    label_key = "search.kind.feedback"
    required_permission = "feedback.read"

    def __init__(self, tickets: TicketService) -> None:
        self.tickets = tickets

    def facets(self) -> Sequence[FacetDef]:
        return (FacetDef("status", "search.facet.state"),)

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        if not query.text.strip() or not await self.tickets.allowed(principal, "feedback.read"):
            return ProviderResult()
        async with self.tickets.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(FeedbackItem).order_by(FeedbackItem.created_at.desc()).limit(500)
                    )
                )
                .scalars()
                .all()
            )
        needle = query.text.strip().casefold()
        matches = [r for r in rows if needle in " ".join(str(v) for v in r.payload.values()).casefold()]
        offset = decode_cursor(cursor)
        items = [
            SearchItem(
                kind=self.kind,
                id=str(r.id),
                title=f"{r.kind} · {r.status}",
                url_ref=f"/support/feedback/{r.id}",
                snippet=snippet(" ".join(str(v) for v in r.payload.values())[:400], query.terms),
            )
            for r in matches[offset : offset + limit]
        ]
        return ProviderResult(
            items=items, next_cursor=encode_cursor(offset + limit) if offset + limit < len(matches) else None
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        return []


def _widget(key: str, permission: str) -> WidgetDefinition:
    name = key.split(".", 1)[1]
    return WidgetDefinition(
        key=key,
        owner=OWNER,
        title_key=f"support:widget.{name}.title",
        description_key=f"support:widget.{name}.description",
        icon="lifebuoy",
        required_permission=permission,
        size=SizeLimits(default=Size(6, 3), min=Size(3, 2), max=Size(12, 6)),
        refresh=Refresh(mode="event", events=("ticket.created", "ticket.state_changed", "ticket.assigned")),
        stale_after_s=600,
        template="list",
    )


MY_TICKETS = _widget("support.my_tickets", TICKETS_CREATE)
QUEUE = _widget("support.queue", TICKETS_MANAGE)


class TicketsWidget:
    def __init__(self, tickets: TicketService, queue: bool, clock: Clock | None = None) -> None:
        self.tickets = tickets
        self.is_queue = queue
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        if self.is_queue:
            rows, _ = await self.tickets.queue(principal, unassigned=True)
            rows = [r for r in rows if r.state not in ("closed", "cancelled", "resolved")]
        else:
            user = self.tickets.user_of(principal)
            rows = (
                [r for r in await self.tickets.mine(user) if r.state not in ("closed", "cancelled")]
                if user
                else []
            )
        if not rows:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        items = [
            {
                "title": r.title,
                "subtitle": f"T-{r.number:06d}",
                "route": f"/support/tickets/{r.id}",
                "state": r.state,  # 027: rendered as a badge
                "at": _when(r),
                "icon": "ticket",
            }
            for r in rows[:8]
        ]
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


def register_actions(tickets: TicketService, incidents: IncidentService, registry: ActionRegistry) -> None:
    async def create_ticket(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        ticket = await tickets.create(
            principal,
            TicketRequest(
                type_key=str(params.get("type", "other")),
                title=str(params["title"]),
                description=str(params.get("description", "")),
                fields=dict(params.get("fields") or {}),
                service_id=params.get("service_id"),
                source="automation",
            ),
        )
        return {"ticket": str(ticket.id), "number": ticket.number}

    async def create_incident(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        if not await tickets.allowed(principal, INCIDENTS_MANAGE):
            raise Forbidden("The automation's author cannot declare incidents.")
        view, created = await incidents.create(
            principal,
            title=str(params["title"]),
            severity=str(params.get("severity", "minor")),
            service_ids=list(params.get("service_ids") or []),
            source="automation",
            dedup_key=str(params["dedup_key"]) if params.get("dedup_key") else None,
            summary=str(params.get("summary", "")),
        )
        return {"incident": str(view.id), "created": created}

    # 027: the parameters are declared, so the automation builder shows a field for each
    for key, description, permission, run, idempotency, params in (
        (
            "ticket.create",
            "Open a support ticket",
            TICKETS_CREATE,
            create_ticket,
            "one ticket per run; dedup by the rule",
            {
                "title": "string",
                "description": "string?",
                "type": "string?",
                "service_id": "uuid?",
                "fields": "object?",
            },
        ),
        (
            "incident.create",
            "Declare an incident",
            INCIDENTS_MANAGE,
            create_incident,
            "idempotent per (automation, dedup_key)",
            {
                "title": "string",
                "severity": "minor|major|critical",
                "summary": "string?",
                "service_ids": "list[uuid]?",
                "dedup_key": "string?",
            },
        ),
    ):
        if registry.get(key) is None:
            registry.register(
                ActionType(
                    key=key,
                    description=description,
                    permission=permission,
                    idempotency=idempotency,
                    run=run,
                    owner=OWNER,
                    params_schema=params,
                    required=("title",),
                )
            )


def _when(row: Any) -> str | None:
    """The last change of a ticket, for the widget row (027)."""
    at = getattr(row, "updated_at", None) or getattr(row, "created_at", None)
    return at.isoformat() if at is not None else None
