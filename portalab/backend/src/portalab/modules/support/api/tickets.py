"""Tickets API (contracts/support-contracts.md, Slice B): precheck, types, creation (optionally from a
diagnosis draft), the requester's tickets, ticket detail, comments, attachments and the staff console
(queue, transitions, assignment, tags, incident link, internal notes, bulk action on an incident's tickets).
Mutations accept ``If-Match: <version>``."""

from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.config import switched_on
from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.support import TicketRequest
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, NotFound, Unavailable
from portalab.modules.support.api.incidents import support_module
from portalab.modules.support.models import Ticket
from portalab.modules.support.module import SupportModule
from portalab.modules.support.permissions import INCIDENTS_MANAGE
from portalab.modules.support.settings import TICKETS_ON
from portalab.modules.support.tickets.service import TICKETS_CREATE, TICKETS_MANAGE, TicketView


async def tickets_on(request: Request) -> None:
    """Issue 246: tickets switched off answer nothing (as an address that does not exist)."""
    if not await switched_on(request.app.state.capabilities, TICKETS_ON):
        raise NotFound("The tickets are switched off.", code="support.tickets_off")


router = APIRouter(prefix="/api/v1", tags=["support"], dependencies=[Depends(tickets_on)])
Module = Annotated[SupportModule, Depends(support_module)]
Requester = Annotated[Principal, require(TICKETS_CREATE)]
Staff = Annotated[Principal, require(TICKETS_MANAGE)]
User = Annotated[Principal, require("users.self.manage")]
IncidentManager = Annotated[Principal, require(INCIDENTS_MANAGE)]
IfMatch = Annotated[str | None, Header(alias="If-Match", max_length=32)]


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


def version_of(if_match: str | None) -> int | None:
    if not if_match:
        return None
    value = if_match.strip().strip('"').removeprefix("W/").strip('"')
    return int(value) if value.isdigit() else None


class TicketPrecheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: str | None = Field(default=None, max_length=64)
    text: str = Field(default="", max_length=4000)


class TicketTypeOut(BaseModel):
    key: str
    label: str
    fields: list[dict[str, Any]]
    media: bool = False  # #354: the type a problem with a media is reported in
    public: bool = False  # #354: its tickets shown to every member on the media's page


class TicketCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type_key: str = Field(max_length=60)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    fields: dict[str, Any] = Field(default_factory=dict)
    service_id: str | None = Field(default=None, max_length=64)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    incident_id: UUID | None = None
    draft_id: UUID | None = None
    media_id: UUID | None = None  # #354: reported from a media's page


class TicketCard(BaseModel):
    id: UUID
    number: int
    reference: str
    title: str
    type_key: str
    state: str
    priority: str
    requester_id: UUID | None
    assignee_id: UUID | None
    incident_id: UUID | None
    service_id: str | None
    updated_at: datetime
    media_id: UUID | None = None


class TicketCommentOut(BaseModel):
    id: UUID
    author_id: UUID | None
    body: str
    internal: bool
    created_at: datetime


class TicketAttachmentOut(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size: int
    private: bool
    created_at: datetime


class TicketHistoryOut(BaseModel):
    seq: int
    kind: str
    actor_id: UUID | None
    data: dict[str, Any]
    created_at: datetime


class TicketDetail(TicketCard):
    description: str
    fields: dict[str, Any]
    field_defs: list[dict[str, Any]]
    tags: list[str]
    version: int
    source: str
    state_label: str
    incident_reference: str | None
    comments: list[TicketCommentOut]
    attachments: list[TicketAttachmentOut]
    history: list[TicketHistoryOut]
    transitions: list[dict[str, Any]]
    staff: bool
    # 027: the feedback it was made from — its form, when, its answers under their labels
    feedback: dict[str, Any] | None = None


class MediaTicketOut(BaseModel):
    """#354: a ticket about a media as its page lists it — its title and state, never who opened it nor
    what they wrote (a public type's tickets are seen by every member)."""

    id: UUID
    reference: str
    title: str
    state: str
    open: bool
    mine: bool
    created_at: datetime
    updated_at: datetime


class MediaTicketsOut(BaseModel):
    open: int
    closed: int
    staff: bool  # the team opens any of them in its queue
    items: list[MediaTicketOut]


class TicketQueueOut(BaseModel):
    items: list[TicketCard]
    next_cursor: str | None


class TicketCommentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=20000)


class TicketTransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transition: str = Field(max_length=40)
    comment: str | None = Field(default=None, max_length=20000)


class TicketAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignee_id: UUID | None = None


class TicketTagsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    add: list[str] = Field(default_factory=list, max_length=20)
    remove: list[str] = Field(default_factory=list, max_length=20)


class TicketIncidentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: UUID | None = None


class IncidentBulkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comment: str = Field(min_length=1, max_length=20000)
    transition: str | None = Field(default=None, max_length=40)
    confirmation: str | None = None


def card(t: Ticket) -> TicketCard:
    return TicketCard(
        id=t.id,
        number=t.number,
        reference=f"T-{t.number:06d}",
        title=t.title,
        type_key=t.type_key,
        state=t.state,
        priority=t.priority,
        requester_id=t.requester_id,
        assignee_id=t.assignee_id,
        incident_id=t.incident_id,
        service_id=t.service_id,
        updated_at=t.updated_at,
        media_id=t.media_id,
    )


def detail(view: TicketView) -> TicketDetail:
    t = view.ticket
    return TicketDetail(
        **card(t).model_dump(),
        description=t.description,
        fields=view.fields,
        field_defs=[d.model_dump() for d in view.field_defs],
        tags=view.tags,
        version=t.version,
        source=t.source,
        state_label=str(view.extra.get("state_label", t.state)),
        incident_reference=f"INC-{view.incident_number:04d}" if view.incident_number else None,
        feedback=view.extra.get("feedback"),
        comments=[
            TicketCommentOut(
                id=c.id, author_id=c.author_id, body=c.body, internal=c.internal, created_at=c.created_at
            )
            for c in view.comments
        ],
        attachments=[
            TicketAttachmentOut(
                id=a.id,
                filename=a.filename,
                content_type=a.content_type,
                size=a.size,
                private=a.private,
                created_at=a.created_at,
            )
            for a in view.attachments
        ],
        history=[
            TicketHistoryOut(
                seq=h.seq, kind=h.kind, actor_id=h.actor_id, data=h.data, created_at=h.created_at
            )
            for h in view.history
        ],
        transitions=view.transitions,
        staff=view.staff,
    )


# --- requesters ------------------------------------------------------------------------------------------
@router.post("/tickets/precheck")
async def precheck(principal: Requester, body: TicketPrecheckIn, module: Module) -> dict[str, Any]:
    return await module.precheck.run(principal, body.service_id, body.text)


@router.get("/tickets/types", response_model=list[TicketTypeOut])
async def types(principal: Requester, module: Module) -> list[TicketTypeOut]:
    staff = await module.tickets.allowed(principal, TICKETS_MANAGE)
    out = []
    for row in await module.definitions.types():
        fields = [f for f in row.fields if staff or f.get("visibility") != "staff_only"]
        out.append(
            TicketTypeOut(key=row.key, label=row.label, fields=fields, media=row.media, public=row.public)
        )
    return out


@router.post("/tickets", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
async def create(principal: Requester, body: TicketCreateIn, module: Module) -> TicketDetail:
    context: dict[str, Any] = {}
    source: Literal["manual", "ai_diagnosis"] = "manual"
    if body.draft_id is not None:
        draft = await module.diagnosis.get_draft(principal, body.draft_id)  # the user reviewed and submits it
        context = {
            "diagnosis_run": str(draft.diagnosis_run_id) if draft.diagnosis_run_id else None,
            "draft": str(draft.id),
        }
        source = "ai_diagnosis"
    ticket = await module.tickets.create(
        principal,
        TicketRequest(
            type_key=body.type_key,
            title=body.title,
            description=body.description,
            fields=body.fields,
            service_id=body.service_id,
            priority=body.priority,
            source=source,
            media_id=body.media_id,
        ),
        incident_id=body.incident_id,
        technical_context=context,
    )
    if body.draft_id is not None:
        await module.diagnosis.consume_draft(body.draft_id)
    return detail(await module.tickets.view(ticket.id, principal))


@router.get("/tickets/media/{media_id}", response_model=MediaTicketsOut)
async def media_tickets(
    principal: Requester, media_id: UUID, module: Module, closed: bool = False
) -> MediaTicketsOut:
    """#354: the tickets about a media I may see — mine, and those of a public type (the team: all); the open
    ones, and the closed ones too on demand."""
    items, still, done, staff = await module.tickets.about_media(principal, media_id, closed=closed)
    return MediaTicketsOut(
        open=still,
        closed=done,
        staff=staff,
        items=[
            MediaTicketOut(
                id=t.id,
                reference=f"T-{t.number:06d}",
                title=t.title,
                state=t.state,
                open=t.resolved_at is None and t.closed_at is None,
                mine=mine,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t, mine in items
        ],
    )


@router.get("/me/tickets", response_model=list[TicketCard])
async def my_tickets(principal: User, module: Module) -> list[TicketCard]:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return [card(t) for t in await module.tickets.mine(user)]


def content_disposition(disposition: str, filename: str) -> str:
    """#280: any name in any script — an ASCII fallback plus the exact name (RFC 6266); a name the header
    cannot carry as is no longer breaks the download."""
    fallback = "".join(c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in filename) or "file"
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


@router.get("/tickets/attachments/{attachment_id}")
async def attachment(principal: User, attachment_id: UUID, module: Module) -> Response:
    file = await module.attachments.read(principal, attachment_id)
    disposition = "inline" if file.inline else "attachment"
    return Response(
        content=file.data,
        media_type=file.content_type,
        headers={
            "Content-Disposition": content_disposition(disposition, file.filename),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(principal: User, ticket_id: UUID, module: Module) -> TicketDetail:
    return detail(await module.tickets.view(ticket_id, principal))


@router.post("/tickets/{ticket_id}/comments", response_model=TicketDetail)
async def comment(
    principal: User, ticket_id: UUID, body: TicketCommentIn, module: Module, if_match: IfMatch = None
) -> TicketDetail:
    await module.tickets.comment(principal, ticket_id, body.body, if_match=version_of(if_match))
    return detail(await module.tickets.view(ticket_id, principal))


@router.post(
    "/tickets/{ticket_id}/attachments",
    response_model=TicketAttachmentOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload(
    principal: User,
    ticket_id: UUID,
    request: Request,
    module: Module,
    filename: Annotated[str, Query(max_length=200)] = "file",
    private: bool = False,
) -> TicketAttachmentOut:
    limit = module.config.attachments_max_bytes
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            from portalab.modules.support.attachments.service import AttachmentRejected

            raise AttachmentRejected("The file is too large.", extensions={"reason": "too_large"})
    row = await module.attachments.upload(principal, ticket_id, bytes(data), filename, private=private)
    return TicketAttachmentOut(
        id=row.id,
        filename=row.filename,
        content_type=row.content_type,
        size=row.size,
        private=row.private,
        created_at=row.created_at,
    )


@router.post("/tickets/{ticket_id}/transition", response_model=TicketDetail)
async def transition(
    principal: User, ticket_id: UUID, body: TicketTransitionIn, module: Module, if_match: IfMatch = None
) -> TicketDetail:
    await module.tickets.transition(
        principal, ticket_id, body.transition, comment=body.comment, if_match=version_of(if_match)
    )
    return detail(await module.tickets.view(ticket_id, principal))


# --- staff ---------------------------------------------------------------------------------------------
@router.get("/support/tickets", response_model=TicketQueueOut)
async def queue(
    principal: Staff,
    module: Module,
    state: Annotated[str | None, Query(max_length=40)] = None,
    assignee: UUID | None = None,
    requester: UUID | None = None,  # one member's tickets (their admin card)
    unassigned: bool = False,
    type_key: Annotated[str | None, Query(alias="type", max_length=60)] = None,
    tag: Annotated[str | None, Query(max_length=60)] = None,
    service: Annotated[str | None, Query(max_length=64)] = None,
    incident: UUID | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
) -> TicketQueueOut:
    rows, next_cursor = await module.tickets.queue(
        principal,
        state=state,
        assignee=assignee,
        requester=requester,
        unassigned=unassigned,
        type_key=type_key,
        tag=tag,
        service=service,
        incident=incident,
        q=q,
        cursor=cursor,
    )
    return TicketQueueOut(items=[card(r) for r in rows], next_cursor=next_cursor)


@router.post("/tickets/{ticket_id}/assign", response_model=TicketDetail)
async def assign(
    principal: Staff, ticket_id: UUID, body: TicketAssignIn, module: Module, if_match: IfMatch = None
) -> TicketDetail:
    await module.tickets.assign(principal, ticket_id, body.assignee_id, if_match=version_of(if_match))
    return detail(await module.tickets.view(ticket_id, principal))


@router.post("/tickets/{ticket_id}/tags", response_model=TicketDetail)
async def tags(principal: Staff, ticket_id: UUID, body: TicketTagsIn, module: Module) -> TicketDetail:
    await module.tickets.set_tags(principal, ticket_id, body.add, body.remove)
    return detail(await module.tickets.view(ticket_id, principal))


@router.post("/tickets/{ticket_id}/link-incident", response_model=TicketDetail)
async def link_incident(
    principal: Staff, ticket_id: UUID, body: TicketIncidentIn, module: Module
) -> TicketDetail:
    await module.tickets.link_incident(principal, ticket_id, body.incident_id)
    return detail(await module.tickets.view(ticket_id, principal))


@router.post("/tickets/{ticket_id}/internal-notes", response_model=TicketDetail)
async def internal_note(
    principal: Staff, ticket_id: UUID, body: TicketCommentIn, module: Module
) -> TicketDetail:
    await module.tickets.comment(principal, ticket_id, body.body, internal=True)
    return detail(await module.tickets.view(ticket_id, principal))


@router.post("/admin/incidents/{incident_id}/tickets/bulk")
async def bulk(
    principal: IncidentManager, incident_id: UUID, body: IncidentBulkIn, module: Module
) -> dict[str, Any]:
    if not await module.tickets.allowed(principal, TICKETS_MANAGE):
        raise Forbidden("You cannot act on tickets.")
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource = ResourceRef("incident", str(incident_id))
    payload = {"comment": body.comment, "transition": body.transition}
    if body.confirmation is None:
        issued = await confirmations.issue(principal, TICKETS_MANAGE, resource, payload)
        raise ConfirmationRequired(
            "This acts on every linked ticket. Confirm to continue.", extensions={"confirmation": issued}
        )
    if not await confirmations.consume(body.confirmation, principal, TICKETS_MANAGE, resource, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
    results = await module.tickets.bulk_for_incident(principal, incident_id, body.comment, body.transition)
    return {"results": results}
