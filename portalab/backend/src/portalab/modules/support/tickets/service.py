"""``TicketService`` (T022, T024, T028; R3, R8, R9, R12, R13): tickets with typed custom fields, a pinned
workflow version, comments (internal notes staff-only), tags, assignment, one optional incident link and an
append-only history. Every mutation writes the ticket row (``version``), its history row and its event in
one transaction; ``If-Match`` versions protect against concurrent edits. Requesters see their own tickets
without staff-only fields, internal notes or private attachments; staff (``tickets.manage``) see all;
closing or reassigning someone else's ticket is audited."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search.fts import decode_cursor, encode_cursor
from portalab.capabilities.support import TicketRef, TicketRequest
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Authorizer, Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.support.admin.definitions import Definitions
from portalab.modules.support.feedback.service import record
from portalab.modules.support.models import (
    Attachment,
    FeedbackItem,
    Incident,
    Ticket,
    TicketComment,
    TicketHistory,
    TicketTag,
)
from portalab.modules.support.settings import SupportConfig
from portalab.modules.support.tickets.notify import ASSIGNMENT, STATUS, SupportNotifier
from portalab.modules.support.workflow.engine import available, check
from portalab.modules.support.workflow.types import FieldDef, parse_fields, validate_values, visible_fields

TICKETS_CREATE = "tickets.create"
TICKETS_COMMENT = "tickets.comment"
TICKETS_MANAGE = "tickets.manage"
PAGE = 50
EVENT_FOR_KIND = {"resolved": "ticket.resolved", "closed": "ticket.closed"}


class TicketNotFound(NotFound):
    default_code = "ticket.not_found"
    default_title = "Ticket not found"


class VersionConflict(Conflict):
    default_code = "ticket.version_conflict"
    default_title = "The ticket changed since you loaded it"


@dataclass
class TicketView:
    ticket: Ticket
    fields: dict[str, Any]
    field_defs: list[FieldDef]
    tags: list[str]
    comments: list[TicketComment]
    attachments: list[Attachment]
    history: list[TicketHistory]
    transitions: list[dict[str, Any]]
    staff: bool
    incident_number: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class TicketService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        definitions: Definitions,
        config: Any,
        notifier: SupportNotifier,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.definitions = definitions
        self.config = config  # callable → SupportConfig
        self.notifier = notifier
        self.clock = clock

    # --- helpers ---------------------------------------------------------------------------------------
    async def allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    @staticmethod
    def user_of(principal: Principal) -> UUID | None:
        return principal.acting_for or principal.user_id

    async def actors(self, ticket: Ticket, principal: Principal) -> set[str]:
        user = self.user_of(principal)
        roles: set[str] = set()
        if user is not None and ticket.requester_id == user:
            roles.add("requester")
        if user is not None and ticket.assignee_id == user:
            roles.add("assignee")
        if await self.allowed(principal, TICKETS_MANAGE):
            roles.add("staff")
        return roles

    async def _load(
        self, session: AsyncSession, ticket_id: UUID, principal: Principal, *, lock: bool = False
    ) -> tuple[Ticket, set[str]]:
        ticket = await session.get(Ticket, ticket_id, with_for_update=lock)
        if ticket is None:
            raise TicketNotFound("This ticket does not exist.")
        roles = await self.actors(ticket, principal)
        if not roles:
            raise TicketNotFound("This ticket does not exist.")  # never reveal someone else's ticket
        return ticket, roles

    @staticmethod
    def _check_version(ticket: Ticket, if_match: int | None) -> None:
        if if_match is not None and if_match != ticket.version:
            raise VersionConflict(
                "Reload the ticket: it changed meanwhile.", extensions={"version": ticket.version}
            )

    async def _history(
        self,
        session: AsyncSession,
        ticket: Ticket,
        kind: str,
        actor: Principal | None,
        data: Mapping[str, Any],
    ) -> int:
        seq = (
            int(
                await session.scalar(
                    select(func.coalesce(func.max(TicketHistory.seq), 0)).where(
                        TicketHistory.ticket_id == ticket.id
                    )
                )
                or 0
            )
            + 1
        )
        session.add(
            TicketHistory(
                ticket_id=ticket.id,
                seq=seq,
                kind=kind,
                actor_id=self.user_of(actor) if actor else None,
                data=dict(data),
                created_at=utc_now(self.clock),
            )
        )
        return seq

    async def _event(self, session: AsyncSession, ticket: Ticket, name: str, seq: int) -> None:
        await self.events.publish(
            session,
            name,
            {
                "ticket": str(ticket.id),
                "seq": seq,
                "state": ticket.state,
                "type": ticket.type_key,
                "priority": ticket.priority,
                "media": ticket.media_id is not None,  # #354: a problem reported on a media
            },
            occurred_at=utc_now(self.clock),
            subject=SubjectRef("user", str(ticket.requester_id)) if ticket.requester_id else None,
            source="support",
            dedup_key=f"{name}:{ticket.id}:{seq}",
        )

    async def _audit(
        self, session: AsyncSession, actor: Principal, action: str, ticket: Ticket, context: dict[str, Any]
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("ticket", str(ticket.id)),
                decision="allow",
                result="success",
                context=context,
                sensitive=True,
            ),
        )

    # --- creation --------------------------------------------------------------------------------------
    async def create(
        self,
        principal: Principal,
        request: TicketRequest,
        *,
        incident_id: UUID | None = None,
        feedback_id: UUID | None = None,
        technical_context: Mapping[str, Any] | None = None,
        requester: UUID | None = None,
    ) -> Ticket:
        if principal.channel == "ai":
            raise Forbidden(
                "The assistant prepares drafts; only the user submits a ticket.",
                code="ticket.ai_cannot_submit",
            )
        if requester is None and not await self.allowed(principal, TICKETS_CREATE):
            raise Forbidden("You cannot open tickets.")
        ticket_type, defs = await self.definitions.ticket_type(request.type_key)
        values = validate_values(defs, request.fields)
        title, description = request.title.strip()[:200], request.description.strip()
        if not title:
            raise ValidationFailed(
                "Give the ticket a title.",
                code="ticket.required_fields_missing",
                extensions={"fields": ["title"]},
            )
        version, workflow = await self.definitions.workflow(ticket_type.workflow_key)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if incident_id is not None and await session.get(Incident, incident_id) is None:
                raise ValidationFailed("This incident does not exist.", code="ticket.unknown_incident")
            number = int(
                (await session.execute(text("SELECT nextval('support.ticket_number_seq')"))).scalar_one()
            )
            ticket = Ticket(
                number=number,
                type_key=ticket_type.key,
                workflow_key=ticket_type.workflow_key,
                workflow_version=version,
                state=workflow.initial,
                title=title,
                description=description,
                requester_id=requester or self.user_of(principal),
                priority=request.priority,
                fields=values,
                service_id=request.service_id,
                incident_id=incident_id,
                media_id=request.media_id,
                source=request.source,
                feedback_id=feedback_id,
                technical_context=dict(technical_context or {}),
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(ticket)
            await session.flush()
            for tag in sorted({t.strip().lower()[:60] for t in request.tags if t.strip()}):
                session.add(TicketTag(ticket_id=ticket.id, tag=tag))
            seq = await self._history(
                session, ticket, "created", principal, {"type": ticket.type_key, "source": ticket.source}
            )
            await self._event(session, ticket, "ticket.created", seq)
            return ticket

    # --- reads -----------------------------------------------------------------------------------------
    async def _follow(self, session: Any, ticket: Ticket, principal: Principal, now: datetime) -> None:
        """027: a ticket made from a feedback closes it when it closes (closed is final: no way back)."""
        item = await session.get(FeedbackItem, ticket.feedback_id, with_for_update=True)
        if item is None:
            return
        label = {"ticket": f"T-{ticket.number:06d}", "id": str(ticket.id)}
        if item.status != "dismissed":
            item.status, item.updated_at = "dismissed", now
            record(session, item.id, "closed", principal, now, detail=label)

    async def _origin(self, item: FeedbackItem) -> dict[str, Any]:
        """027: the feedback a ticket was made from — its form, when, and its answers under their labels."""
        labels: dict[str, str] = {}
        name = item.form_key
        try:
            form, defs = await self.definitions.form(item.form_key)
            name, labels = form.label, {d.key: d.label for d in defs}
        except Exception:  # noqa: S110 — a form since removed: the keys stand for its labels
            pass
        answers = [
            {
                "label": labels.get(key, key),
                "value": ", ".join(map(str, v)) if isinstance(v, list) else str(v),
            }
            for key, v in item.payload.items()
            if v not in (None, "", [])
        ]
        return {
            "id": str(item.id),
            "form": name,
            "kind": item.kind,
            "at": item.created_at.isoformat(),
            "answers": answers,
        }

    async def view(self, ticket_id: UUID, viewer: Principal) -> TicketView:
        async with self.database.session() as session:
            ticket, roles = await self._load(session, ticket_id, viewer)
            staff = "staff" in roles
            comments = list(
                (
                    await session.execute(
                        select(TicketComment)
                        .where(
                            TicketComment.ticket_id == ticket.id,
                            or_(TicketComment.internal.is_(False), literal(staff)),
                        )
                        .order_by(TicketComment.created_at)
                    )
                )
                .scalars()
                .all()
            )
            attachments = list(
                (
                    await session.execute(
                        select(Attachment)
                        .where(
                            Attachment.ticket_id == ticket.id,
                            or_(Attachment.private.is_(False), literal(staff)),
                        )
                        .order_by(Attachment.created_at)
                    )
                )
                .scalars()
                .all()
            )
            history = list(
                (
                    await session.execute(
                        select(TicketHistory)
                        .where(TicketHistory.ticket_id == ticket.id)
                        .order_by(TicketHistory.seq)
                    )
                )
                .scalars()
                .all()
            )
            tags = [
                r[0]
                for r in await session.execute(
                    select(TicketTag.tag).where(TicketTag.ticket_id == ticket.id).order_by(TicketTag.tag)
                )
            ]
            incident = await session.get(Incident, ticket.incident_id) if ticket.incident_id else None
            incident_number = incident.number if incident is not None else None
            origin = await session.get(FeedbackItem, ticket.feedback_id) if ticket.feedback_id else None
        if not staff:
            history = [h for h in history if not (h.kind == "comment_added" and h.data.get("internal"))]
        ticket_type, defs = await self._type_defs(ticket.type_key)
        _, workflow = await self.definitions.workflow(ticket.workflow_key, ticket.workflow_version)
        moves = available(workflow, ticket.state, roles, reopen_open=self._reopen_open(ticket))
        return TicketView(
            ticket=ticket,
            fields=visible_fields(defs, ticket.fields, staff=staff),
            field_defs=[d for d in defs if staff or d.visibility != "staff_only"],
            tags=tags,
            comments=comments,
            attachments=attachments,
            history=history,
            transitions=[
                {"key": t.key, "label": t.label, "comment_required": t.comment_required} for t in moves
            ],
            staff=staff,
            incident_number=incident_number,
            extra={
                "state_label": getattr(workflow.state(ticket.state), "label", ticket.state),
                "type_label": ticket_type,
                **({"feedback": await self._origin(origin)} if origin is not None else {}),
            },
        )

    async def _type_defs(self, key: str) -> tuple[str, list[FieldDef]]:
        from portalab.modules.support.models import TicketType

        async with self.database.session() as session:
            row = await session.get(TicketType, key)
        return (row.label, parse_fields(row.fields)) if row is not None else (key, [])

    def _reopen_open(self, ticket: Ticket) -> bool:
        config: SupportConfig = self.config()
        if ticket.resolved_at is None:
            return True
        return utc_now(self.clock) - ticket.resolved_at <= timedelta(days=max(0, config.reopen_window_days))

    async def mine(self, user: UUID) -> list[Ticket]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Ticket)
                        .where(Ticket.requester_id == user)
                        .order_by(Ticket.updated_at.desc())
                        .limit(200)
                    )
                )
                .scalars()
                .all()
            )

    async def queue(
        self,
        viewer: Principal,
        *,
        state: str | None = None,
        assignee: UUID | None = None,
        requester: UUID | None = None,
        unassigned: bool = False,
        type_key: str | None = None,
        tag: str | None = None,
        service: str | None = None,
        incident: UUID | None = None,
        q: str | None = None,
        cursor: str | None = None,
    ) -> tuple[list[Ticket], str | None]:
        if not await self.allowed(viewer, TICKETS_MANAGE):
            raise Forbidden("You cannot see the support queue.")
        stmt = select(Ticket)
        filters = []
        if state:
            filters.append(Ticket.state == state)
        if assignee:
            filters.append(Ticket.assignee_id == assignee)
        if requester:
            filters.append(Ticket.requester_id == requester)
        if unassigned:
            filters.append(Ticket.assignee_id.is_(None))
        if type_key:
            filters.append(Ticket.type_key == type_key)
        if service:
            filters.append(Ticket.service_id == service)
        if incident:
            filters.append(Ticket.incident_id == incident)
        if tag:
            filters.append(Ticket.id.in_(select(TicketTag.ticket_id).where(TicketTag.tag == tag.lower())))
        if q:
            needle = f"%{q.strip()[:80]}%"
            filters.append(or_(Ticket.title.ilike(needle), Ticket.description.ilike(needle)))
        if filters:
            stmt = stmt.where(and_(*filters))
        offset = decode_cursor(cursor)
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        stmt.order_by(Ticket.updated_at.desc(), Ticket.id).offset(offset).limit(PAGE + 1)
                    )
                )
                .scalars()
                .all()
            )
        return rows[:PAGE], encode_cursor(offset + PAGE) if len(rows) > PAGE else None

    # --- mutations -------------------------------------------------------------------------------------
    async def comment(
        self,
        principal: Principal,
        ticket_id: UUID,
        body: str,
        *,
        internal: bool = False,
        if_match: int | None = None,
    ) -> TicketComment:
        text_body = body.strip()
        if not text_body or len(text_body) > 20000:
            raise ValidationFailed(
                "Write a comment (at most 20 000 characters).", code="ticket.invalid_comment"
            )
        async with self.database.unit_of_work() as uow:
            session = uow.session
            ticket, roles = await self._load(session, ticket_id, principal, lock=True)
            self._check_version(ticket, if_match)
            if internal and "staff" not in roles:
                raise Forbidden("Only support staff write internal notes.")
            if "staff" not in roles and not await self.allowed(principal, TICKETS_COMMENT):
                raise Forbidden("You cannot comment on tickets.")
            comment = TicketComment(
                ticket_id=ticket.id,
                author_id=self.user_of(principal),
                body=text_body,
                internal=internal,
                created_at=utc_now(self.clock),
            )
            session.add(comment)
            await session.flush()
            ticket.version, ticket.updated_at = ticket.version + 1, utc_now(self.clock)
            seq = await self._history(
                session,
                ticket,
                "comment_added",
                principal,
                {"comment": str(comment.id), "internal": internal},
            )
            await self._event(session, ticket, "ticket.updated", seq)
            requester, assignee, number = ticket.requester_id, ticket.assignee_id, ticket.number
        if not internal:
            author = self.user_of(principal)
            target = requester if author != requester else assignee
            await self.notifier.send(
                STATUS,
                "support:notify.comment",
                target,
                f"ticket:{ticket_id}:{seq}:comment",
                {"number": number},
                f"/support/tickets/{ticket_id}",
            )
        return comment

    async def transition(
        self,
        principal: Principal,
        ticket_id: UUID,
        key: str,
        *,
        comment: str | None = None,
        if_match: int | None = None,
    ) -> Ticket:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            ticket, roles = await self._load(session, ticket_id, principal, lock=True)
            self._check_version(ticket, if_match)
            _, workflow = await self.definitions.workflow(ticket.workflow_key, ticket.workflow_version)
            move = check(
                workflow,
                ticket.state,
                key,
                roles,
                has_comment=bool(comment and comment.strip()),
                reopen_open=self._reopen_open(ticket),
            )
            previous = ticket.state
            now = utc_now(self.clock)
            if comment and comment.strip():
                session.add(
                    TicketComment(
                        ticket_id=ticket.id,
                        author_id=self.user_of(principal),
                        body=comment.strip()[:20000],
                        internal=False,
                        created_at=now,
                    )
                )
            ticket.state = move.target.key
            ticket.version, ticket.updated_at = ticket.version + 1, now
            if move.target.kind == "resolved":
                ticket.resolved_at = now
            if move.target.kind == "closed":
                ticket.closed_at = now
            if move.transition.reopen:
                ticket.resolved_at = ticket.closed_at = None
            seq = await self._history(
                session,
                ticket,
                "transition",
                principal,
                {"from": previous, "to": ticket.state, "transition": key},
            )
            await self._event(session, ticket, "ticket.state_changed", seq)
            if ticket.feedback_id is not None and move.target.kind == "closed":  # 027: its feedback follows
                await self._follow(session, ticket, principal, now)
            if move.transition.reopen:
                await self._event(session, ticket, "ticket.reopened", seq)
            special = EVENT_FOR_KIND.get(move.target.kind)
            if special:
                await self._event(session, ticket, special, seq)
            if move.target.kind == "closed" and "requester" not in roles:
                await self._audit(
                    session, principal, "ticket.closed_for_requester", ticket, {"state": ticket.state}
                )
            requester, number, state = ticket.requester_id, ticket.number, ticket.state
        if self.user_of(principal) != requester:
            await self.notifier.send(
                STATUS,
                "support:notify.state",
                requester,
                f"ticket:{ticket_id}:{seq}:state",
                {"number": number, "state": move.target.label},
                f"/support/tickets/{ticket_id}",
            )
        del state
        return ticket

    async def assign(
        self, principal: Principal, ticket_id: UUID, assignee: UUID | None, *, if_match: int | None = None
    ) -> Ticket:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            ticket, roles = await self._load(session, ticket_id, principal, lock=True)
            if "staff" not in roles:
                raise Forbidden("Only support staff assign tickets.")
            self._check_version(ticket, if_match)
            previous = ticket.assignee_id
            ticket.assignee_id = assignee
            ticket.version, ticket.updated_at = ticket.version + 1, utc_now(self.clock)
            seq = await self._history(
                session,
                ticket,
                "assignment",
                principal,
                {"from": str(previous) if previous else None, "to": str(assignee) if assignee else None},
            )
            await self._event(session, ticket, "ticket.assigned", seq)
            if previous is not None and previous != assignee and previous != self.user_of(principal):
                await self._audit(
                    session,
                    principal,
                    "ticket.reassigned",
                    ticket,
                    {"to": str(assignee) if assignee else None},
                )
            number = ticket.number
        if assignee is not None and assignee != self.user_of(principal):
            await self.notifier.send(
                ASSIGNMENT,
                "support:notify.assigned",
                assignee,
                f"ticket:{ticket_id}:{seq}:assigned",
                {"number": number},
                f"/support/tickets/{ticket_id}",
            )
        return ticket

    async def set_tags(
        self, principal: Principal, ticket_id: UUID, add: Sequence[str], remove: Sequence[str]
    ) -> list[str]:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            ticket, roles = await self._load(session, ticket_id, principal, lock=True)
            if "staff" not in roles:
                raise Forbidden("Only support staff tag tickets.")
            gone = {t.strip().lower() for t in remove if t.strip()}
            if gone:
                await session.execute(
                    delete(TicketTag).where(TicketTag.ticket_id == ticket.id, TicketTag.tag.in_(gone))
                )
            existing = {
                r[0]
                for r in await session.execute(select(TicketTag.tag).where(TicketTag.ticket_id == ticket.id))
            }
            for tag in sorted({t.strip().lower()[:60] for t in add if t.strip()} - existing):
                session.add(TicketTag(ticket_id=ticket.id, tag=tag))
            ticket.version, ticket.updated_at = ticket.version + 1, utc_now(self.clock)
            seq = await self._history(
                session, ticket, "tag", principal, {"added": sorted(add), "removed": sorted(remove)}
            )
            await self._event(session, ticket, "ticket.updated", seq)
            await session.flush()
            return [
                r[0]
                for r in await session.execute(
                    select(TicketTag.tag).where(TicketTag.ticket_id == ticket.id).order_by(TicketTag.tag)
                )
            ]

    async def link_incident(self, principal: Principal, ticket_id: UUID, incident_id: UUID | None) -> Ticket:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            ticket, roles = await self._load(session, ticket_id, principal, lock=True)
            if "staff" not in roles:
                raise Forbidden("Only support staff link tickets to incidents.")
            if incident_id is not None and await session.get(Incident, incident_id) is None:
                raise ValidationFailed("This incident does not exist.", code="ticket.unknown_incident")
            ticket.incident_id = incident_id  # a ticket references at most one incident (R8)
            ticket.version, ticket.updated_at = ticket.version + 1, utc_now(self.clock)
            seq = await self._history(
                session,
                ticket,
                "incident_linked",
                principal,
                {"incident": str(incident_id) if incident_id else None},
            )
            await self._event(session, ticket, "ticket.updated", seq)
            return ticket

    async def bulk_for_incident(
        self, principal: Principal, incident_id: UUID, comment: str, transition: str | None
    ) -> list[dict[str, Any]]:
        """Support action after an incident: comment (and optionally transition) every linked ticket, with a
        per-ticket outcome. Incident resolution itself never touches tickets (R8)."""
        if not await self.allowed(principal, TICKETS_MANAGE):
            raise Forbidden("You cannot act on tickets.")
        async with self.database.session() as session:
            ids = [
                r[0]
                for r in await session.execute(
                    select(Ticket.id).where(Ticket.incident_id == incident_id).order_by(Ticket.number)
                )
            ]
        results: list[dict[str, Any]] = []
        for ticket_id in ids:
            try:
                if transition:
                    await self.transition(principal, ticket_id, transition, comment=comment)
                else:
                    await self.comment(principal, ticket_id, comment)
                results.append({"ticket": str(ticket_id), "ok": True})
            except Exception as exc:  # each ticket stands alone
                results.append(
                    {"ticket": str(ticket_id), "ok": False, "error": getattr(exc, "code", type(exc).__name__)}
                )
        async with self.database.unit_of_work() as uow:
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="incident.tickets_bulk",
                    actor=principal,
                    resource=ResourceRef("incident", str(incident_id)),
                    decision="allow",
                    result="success",
                    context={
                        "tickets": len(ids),
                        "failed": sum(1 for r in results if not r["ok"]),
                        "transition": transition,
                    },
                    sensitive=True,
                ),
            )
        return results


class TicketsPortImpl:
    """``support.tickets``: the same rules for every caller — an automation acts for its author, the AI only
    prepares drafts (refused here)."""

    def __init__(self, service: TicketService) -> None:
        self.service = service

    async def create(self, request: TicketRequest, principal: Principal) -> TicketRef:
        ticket = await self.service.create(principal, request)
        return TicketRef(ticket.id, ticket.number, ticket.state, f"/support/tickets/{ticket.id}")

    async def get_for_viewer(self, ticket_id: UUID, viewer: Principal) -> TicketRef | None:
        try:
            view = await self.service.view(ticket_id, viewer)
        except TicketNotFound:
            return None
        t = view.ticket
        return TicketRef(t.id, t.number, t.state, f"/support/tickets/{t.id}")
