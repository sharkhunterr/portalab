"""The assistant's support tools (issue 171), each run as the member it acts for — their own tickets only
(or, for the support staff, those the ticket rules let them see):

* ``support.my_tickets``: the member's tickets — number, title, state, last change;
* ``support.ticket``: one ticket by its number — its state, its fields, the last public replies (never the
  staff's internal notes);
* ``support.create_ticket``: a ticket the assistant proposes — Portalab shows the member its exact title and
  description in the conversation, and only their « Confirm » opens it, in their name (a sensitive action:
  it never runs inline; the assistant alone still cannot submit one: ``ticket.ai_cannot_submit``)."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.ai import AITool, AIToolRegistry, SourceRef, ToolResult
from portalab.capabilities.health import SERVICE_DIRECTORY
from portalab.capabilities.support import TicketRequest
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.support.models import Ticket
from portalab.modules.support.permissions import INCIDENTS_READ
from portalab.modules.support.tickets.service import TICKETS_CREATE

OWNER = "module:support"
MAX_TICKETS = 15
MAX_REPLIES = 4


def _number(value: Any) -> int | None:
    text = str(value or "").strip().lstrip("#")
    return int(text) if text.isdigit() else None


class SupportAiTools:
    def __init__(self, module: Any, clock: Clock | None = None) -> None:
        self.module = module
        self.clock = clock

    def _source(self, ticket: Ticket) -> SourceRef:
        return SourceRef(
            "ticket",
            f"ticket:{ticket.id}",
            f"#{ticket.number} {ticket.title}",
            "real",
            utc_now(self.clock),
            f"/support/tickets/{ticket.id}",
            detail=f"#{ticket.number} · {ticket.state}",
        )

    async def my_tickets(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        user = principal.acting_for or principal.user_id
        if user is None:
            return ToolResult("unavailable", {"tickets": []})
        rows = await self.module.tickets.mine(user)
        state = str(params.get("state") or "").strip().lower()
        if state == "open":
            rows = [t for t in rows if t.resolved_at is None]
        elif state == "resolved":
            rows = [t for t in rows if t.resolved_at is not None]
        rows = rows[:MAX_TICKETS]
        return ToolResult(
            "ok",
            {
                "tickets": [
                    {
                        "number": t.number,
                        "title": t.title,
                        "state": t.state,
                        "priority": t.priority,
                        "updated_at": t.updated_at.isoformat(),
                        "resolved": t.resolved_at is not None,
                    }
                    for t in rows
                ]
            },
            [self._source(t) for t in rows[:5]],
        )

    async def ticket(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        number = _number(params.get("number"))
        wanted = str(params.get("id") or "").strip()
        if number is None and not wanted:
            return ToolResult("error", {"error": "give the ticket's number or id"})
        async with self.module.database.session() as session:
            if wanted:  # the page the member is on names it (« ticket id=… »)
                try:
                    found = await session.scalar(select(Ticket.id).where(Ticket.id == UUID(wanted)))
                except ValueError:
                    found = None
            else:
                found = await session.scalar(select(Ticket.id).where(Ticket.number == number))
        if found is None:
            return ToolResult("ok", {"found": False, "number": number or wanted})
        try:
            view = await self.module.tickets.view(found, principal)  # its own rules: whose ticket it is
        except NotFound:
            return ToolResult("ok", {"found": False, "number": number or wanted})
        ticket = view.ticket
        replies = [c for c in view.comments if not c.internal][-MAX_REPLIES:]
        return ToolResult(
            "ok",
            {
                "found": True,
                "number": ticket.number,
                "title": ticket.title,
                "state": ticket.state,
                "priority": ticket.priority,
                "created_at": ticket.created_at.isoformat(),
                "updated_at": ticket.updated_at.isoformat(),
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                "description": ticket.description[:1500],
                "fields": {k: v for k, v in view.fields.items() if isinstance(v, str | int | float | bool)},
                "last_replies": [
                    {
                        "at": c.created_at.isoformat(),
                        "from_requester": c.author_id == ticket.requester_id,
                        "text": c.body[:600],
                    }
                    for c in replies
                ],
                "next_states": [str(t.get("to") or t.get("key") or "") for t in view.transitions][:6],
            },
            [self._source(ticket)],
        )

    async def _type(self, wanted: Any) -> str:
        types = [t.key for t in await self.module.definitions.types()]
        key = str(wanted or "").strip()
        return key if key in types else ("other" if "other" in types else (types[0] if types else "other"))

    async def create_ticket(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        """Runs only once the member confirmed it (a sensitive tool never runs inline): theirs, then."""
        title = str(params.get("title") or "").strip()[:200]
        description = str(params.get("description") or "").strip()[:4000]
        member = principal.acting_for or principal.user_id
        if not title or not description or member is None:
            return ToolResult("error", {"error": "a ticket needs a title and a description"})
        try:
            ticket = await self.module.tickets.create(
                Principal(user_id=member),  # the member confirmed this very content in Portalab
                TicketRequest(
                    await self._type(params.get("type")), title, description, {}, source="ai_diagnosis"
                ),
                technical_context={"opened_by": "assistant, confirmed by the member"},
            )
        except ValidationFailed as refused:  # a kind of ticket asking for more: the form says what
            return ToolResult(
                "error",
                {"error": str(refused), "missing": refused.extensions.get("fields"), "form": "/support/new"},
            )
        return ToolResult(
            "ok",
            {"created": True, "number": ticket.number, "state": ticket.state},
            [self._source(ticket)],
        )

    # --- issue 171: the incidents (what is wrong, where it stands, what was fixed lately) ------------------
    async def _service_names(self) -> dict[str, str]:
        try:
            providers = self.module.capabilities.system_providers(SERVICE_DIRECTORY)
            if not providers:
                return {}
            return {s.id: s.name for s in await providers[0].provider.services()}
        except Exception:
            return {}

    async def incidents(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        if not await self.module.tickets.allowed(principal, INCIDENTS_READ):
            return ToolResult("unavailable", {"incidents": []})
        names = await self._service_names()
        now = utc_now(self.clock)
        opened = await self.module.incidents.list(state="open", limit=10)
        ongoing = []
        for view in opened:
            full = await self.module.incidents.get(view.id)  # its timeline: the last word on it
            last = full.updates[-1] if full.updates else None
            ongoing.append(
                {
                    "reference": view.reference,
                    "title": view.title,
                    "severity": view.severity,
                    "stage": view.state,
                    "since": view.created_at.isoformat(),
                    "services": [names.get(s, s) for s in view.service_ids][:8] or ["the whole portal"],
                    "summary": view.summary[:300] or None,
                    "last_update": (last or {}).get("message", "")[:300] or None,
                }
            )
        recent = [
            {"reference": v.reference, "title": v.title, "resolved_at": v.resolved_at.isoformat()}
            for v in await self.module.incidents.list(state="resolved", limit=10)
            if v.resolved_at is not None and now - v.resolved_at <= timedelta(days=7)
        ][:5]
        sources = [
            SourceRef(
                "incident",
                f"incident:{v.id}",
                f"{v.reference} {v.title}",
                "real",
                now,
                f"/incidents/{v.id}",
                detail=f"{v.severity} · {v.state}",
            )
            for v in opened
        ]
        summary = (f"{len(ongoing)} incident(s) in progress." if ongoing else "No incident in progress.") + (
            f" {len(recent)} resolved in the last 7 days." if recent else ""
        )
        return ToolResult(
            "ok", {"summary": summary, "in_progress": ongoing, "resolved_lately": recent}, sources
        )

    def tools(self) -> list[AITool]:
        def schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": properties,
                **({"required": required} if required else {}),
                "additionalProperties": False,
            }

        return [
            AITool(
                "incidents.current",
                "The portal's incidents: those in progress (severity, stage, the services hit, the last "
                "update) and those resolved in the last days — what is wrong now, beyond the probes.",
                schema({}),
                INCIDENTS_READ,
                "read",
                self.incidents,
                owner=OWNER,
            ),
            AITool(
                "support.my_tickets",
                "The user's own support tickets (number, title, state, last change); optionally only open or "
                "resolved ones.",
                schema({"state": {"type": "string", "enum": ["open", "resolved", "all"]}}),
                TICKETS_CREATE,
                "read",
                self.my_tickets,
                owner=OWNER,
            ),
            AITool(
                "support.ticket",
                "One support ticket by its number (or its id, when the user is on its page): state, "
                "description, fields and the last public replies.",
                schema(
                    {
                        "number": {"type": "integer", "minimum": 1},
                        "id": {"type": "string", "format": "uuid"},
                    }
                ),
                TICKETS_CREATE,
                "read",
                self.ticket,
                owner=OWNER,
            ),
            AITool(
                "support.create_ticket",
                "Open a support ticket for the user (title, description, optional type). The portal shows "
                "the user its exact content and opens it only when they confirm: say so, never claim it is "
                "open before.",
                schema(
                    {
                        "title": {"type": "string", "minLength": 3, "maxLength": 200},
                        "description": {"type": "string", "minLength": 3, "maxLength": 4000},
                        "type": {"type": "string", "maxLength": 64},
                    },
                    ["title", "description"],
                ),
                TICKETS_CREATE,
                "sensitive",
                self.create_ticket,
                summarize=lambda params: (
                    f"Open the ticket « {str(params.get('title') or '')[:120]} » — "
                    f"{str(params.get('description') or '')[:240]}"
                ),
                owner=OWNER,
            ),
        ]

    def register(self, registry: AIToolRegistry) -> None:
        for tool in self.tools():
            if registry.get(tool.name) is None:
                registry.register(tool)
