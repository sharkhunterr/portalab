"""Feedback conversion (T032; R10): an explicit staff action creating the target **in its owning domain**
through a port — a ticket here, a contribution in Gamification (013), a feature proposal or a community
project in Community (012). The provenance is kept (``feedback_conversions``, one per feedback and target
kind: converting twice returns the first result); the original feedback is never deleted; a target whose
port is absent is offered disabled with a reason."""

import asyncio
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.support import CONTRIBUTIONS, PROPOSALS, TicketRequest
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.errors import Forbidden, Unavailable
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.support.feedback.service import FeedbackNotFound, record
from portalab.modules.support.models import FeedbackConversion, FeedbackItem, Ticket
from portalab.modules.support.tickets.service import TicketService

Target = Literal["ticket", "contribution", "feature_proposal", "community_project"]
TARGETS: tuple[Target, ...] = ("ticket", "contribution", "feature_proposal", "community_project")
PERMISSION = {
    "ticket": "feedback.convert",
    "feature_proposal": "feedback.convert",
    "community_project": "feedback.convert",
    "contribution": "feedback.convert.contribution",
}
SENSITIVE = ("contribution", "community_project")


class ConversionUnavailable(Unavailable):
    default_code = "feedback.conversion_unavailable"
    default_title = "This conversion is not available"


@dataclass(frozen=True, slots=True)
class ConversionOption:
    target: str
    available: bool
    reason: str | None = None
    done: str | None = None  # target_ref when already converted


def _title(item: FeedbackItem) -> str:
    for key in ("what", "idea", "message"):
        value = item.payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().splitlines()[0][:200]
    return f"Feedback {item.kind}"


def _body(item: FeedbackItem) -> str:
    return "\n\n".join(f"**{key}**: {value}" for key, value in item.payload.items())


class ConversionService:
    def __init__(
        self,
        tickets: TicketService,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.tickets = tickets
        self.events = events
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock

    def _port(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def options(self, viewer: Principal, feedback_id: UUID) -> list[ConversionOption]:
        async with self.tickets.database.session() as session:
            done = {
                c.target_kind: c.target_ref
                for c in (
                    await session.execute(
                        select(FeedbackConversion).where(FeedbackConversion.feedback_id == feedback_id)
                    )
                ).scalars()
            }
        out = []
        for target in TARGETS:
            reason = None
            if not await self._allowed(viewer, PERMISSION[target]):
                reason = "permission"
            elif target == "contribution" and self._port(CONTRIBUTIONS) is None:
                reason = "gamification_unavailable"
            elif target in ("feature_proposal", "community_project") and self._port(PROPOSALS) is None:
                reason = "community_unavailable"
            out.append(ConversionOption(target, reason is None, reason, done.get(target)))
        return out

    async def _allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    async def convert(self, actor: Principal, feedback_id: UUID, target: Target) -> FeedbackConversion:
        if target not in TARGETS:
            raise ConversionUnavailable("Unknown conversion.", extensions={"reason": "unknown"})
        if not await self._allowed(actor, PERMISSION[target]):
            raise Forbidden("You cannot perform this conversion.")
        database = self.tickets.database
        async with database.session() as session:
            item = await session.get(FeedbackItem, feedback_id)
            if item is None:
                raise FeedbackNotFound("This feedback does not exist.")
            existing = (
                await session.execute(
                    select(FeedbackConversion).where(
                        FeedbackConversion.feedback_id == feedback_id,
                        FeedbackConversion.target_kind == target,
                    )
                )
            ).scalar_one_or_none()
        if existing is not None:
            return existing  # converting twice yields the first result (contribution credited once)
        ref = await self._create(actor, item, target)
        now = utc_now(self.clock)
        async with database.unit_of_work() as uow:
            row = FeedbackConversion(
                feedback_id=feedback_id,
                target_kind=target,
                target_ref=ref,
                converted_by=actor.acting_for or actor.user_id,
                converted_at=now,
            )
            uow.session.add(row)
            locked = await uow.session.get(FeedbackItem, feedback_id, with_for_update=True)
            if locked is not None:
                locked.status, locked.updated_at = "converted", now
            detail: dict[str, Any] = {"target": target, "ref": ref}
            if ref.startswith("portalab://ticket/"):  # the ticket's reference, as the staff knows it
                ticket = await uow.session.get(Ticket, UUID(ref.rsplit("/", 1)[1]))
                if ticket is not None:
                    detail["label"] = f"T-{ticket.number:06d}"
                    detail["id"] = str(ticket.id)
            record(uow.session, feedback_id, "converted", actor, now, detail=detail)
            await self.events.publish(
                uow.session,
                "feedback.converted",
                {"feedback": str(feedback_id), "kind": item.kind, "target": target},
                occurred_at=now,
                source="support",
                dedup_key=f"feedback.converted:{feedback_id}:{target}",
            )
            return row

    async def _create(self, actor: Principal, item: FeedbackItem, target: Target) -> str:
        provenance = f"portalab://feedback/{item.id}"
        if target == "ticket":
            ticket = await self.tickets.create(
                actor,
                TicketRequest(
                    type_key="bug" if item.kind == "bug_report" else "question",
                    title=_title(item),
                    description=_body(item),
                    fields={"steps": str(item.payload.get("steps") or item.payload.get("what") or "-")}
                    if item.kind == "bug_report"
                    else {},
                    source="feedback_conversion",
                ),
                feedback_id=item.id,
                requester=item.submitter_id or (actor.acting_for or actor.user_id),
                technical_context={"provenance": provenance},
            )
            return f"portalab://ticket/{ticket.id}"
        if target == "contribution":
            port = self._port(CONTRIBUTIONS)
            if port is None or item.submitter_id is None:
                raise ConversionUnavailable(
                    "Contributions are not available.", extensions={"reason": "gamification_unavailable"}
                )
            return str(
                await asyncio.wait_for(
                    port.grant_contribution(item.submitter_id, "feedback", provenance, actor), timeout=10
                )
            )
        port = self._port(PROPOSALS)
        if port is None:
            raise ConversionUnavailable(
                "Community proposals are not available.", extensions={"reason": "community_unavailable"}
            )
        kind: Literal["feature", "project"] = "feature" if target == "feature_proposal" else "project"
        return str(
            await asyncio.wait_for(
                port.create(kind, _title(item), _body(item), item.submitter_id, provenance, actor), timeout=10
            )
        )
