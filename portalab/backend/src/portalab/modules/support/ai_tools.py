"""The assistant's support tools (issue 171), each run as the member it acts for — their own tickets only
(or, for the support staff, those the ticket rules let them see):

* ``support.my_tickets``: the member's tickets — number, title, state, last change;
* ``support.ticket``: one ticket by its number — its state, its fields, the last public replies (never the
  staff's internal notes);
* ``support.draft_ticket``: a ticket the assistant prepares — the member opens it in the ticket form, reads
  it and submits it (the assistant never submits a ticket: ``ticket.ai_cannot_submit``)."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.ai import AITool, AIToolRegistry, SourceRef, ToolResult
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.core.time import Clock, utc_now
from portalab.modules.support.models import Ticket
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

    async def draft_ticket(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        title = str(params.get("title") or "").strip()[:200]
        description = str(params.get("description") or "").strip()[:4000]
        if not title or not description:
            return ToolResult("error", {"error": "a ticket needs a title and a description"})
        types = [t.key for t in await self.module.definitions.types()]
        wanted = str(params.get("type") or "").strip()
        type_key = (
            wanted if wanted in types else ("other" if "other" in types else (types[0] if types else "other"))
        )
        draft = await self.module.diagnosis.prepare(
            principal, {"type_key": type_key, "title": title, "description": description, "fields": {}}
        )
        url = f"/support/new?draft={draft.id}"
        return ToolResult(
            "ok",
            {
                "draft": str(draft.id),
                "url": url,
                "type": type_key,
                "created": False,
                "sent": False,
                "note": "Only a draft: no ticket exists yet. The user opens this link, reads the ticket and "
                "sends it.",
            },
            [SourceRef("ticket_draft", f"ticket_draft:{draft.id}", title, "real", utc_now(self.clock), url)],
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
                "support.draft_ticket",
                "Prepare a support ticket for the user (title, description, optional type). It is NOT sent: "
                "give the user the returned link to review and submit it.",
                schema(
                    {
                        "title": {"type": "string", "minLength": 3, "maxLength": 200},
                        "description": {"type": "string", "minLength": 3, "maxLength": 4000},
                        "type": {"type": "string", "maxLength": 64},
                    },
                    ["title", "description"],
                ),
                TICKETS_CREATE,
                "write",
                self.draft_ticket,
                summarize=lambda params: f"Prepare the ticket « {str(params.get('title') or '')[:80]} »",
                owner=OWNER,
            ),
        ]

    def register(self, registry: AIToolRegistry) -> None:
        for tool in self.tools():
            if registry.get(tool.name) is None:
                registry.register(tool)
