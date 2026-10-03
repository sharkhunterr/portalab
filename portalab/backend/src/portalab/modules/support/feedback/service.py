"""Feedback (T030; R10): admin-defined forms (seeded ``general``, ``bug_report``, ``feature_request``) with
validated structured fields; a submission is a ``feedback_item`` — **never** a ticket by itself. Staff with
``feedback.read`` review or dismiss; form versions are pinned on each item."""

from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.support.admin.definitions import Definitions
from portalab.modules.support.models import FeedbackConversion, FeedbackItem
from portalab.modules.support.workflow.types import validate_values

FEEDBACK_SUBMIT = "feedback.submit"
FEEDBACK_READ = "feedback.read"


class FeedbackNotFound(NotFound):
    default_code = "feedback.not_found"
    default_title = "Feedback not found"


class FeedbackService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        authorizer: Authorizer,
        definitions: Definitions,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.authorizer = authorizer
        self.definitions = definitions
        self.clock = clock

    async def _allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    async def submit(self, principal: Principal, form_key: str, values: dict[str, Any]) -> FeedbackItem:
        if not await self._allowed(principal, FEEDBACK_SUBMIT):
            raise Forbidden("You cannot send feedback.")
        form, defs = await self.definitions.form(form_key)
        payload = validate_values(defs, values)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            item = FeedbackItem(
                form_key=form.key,
                form_version=form.version,
                kind=form.kind,
                submitter_id=principal.acting_for or principal.user_id,
                payload=payload,
                status="new",
                created_at=now,
                updated_at=now,
            )
            uow.session.add(item)
            await uow.session.flush()
            await self.events.publish(
                uow.session,
                "feedback.submitted",
                {"feedback": str(item.id), "kind": item.kind, "target": "submitted"},
                occurred_at=now,
                source="support",
                dedup_key=f"feedback.submitted:{item.id}",
            )
            return item

    async def listing(
        self, viewer: Principal, *, status: str | None = None, kind: str | None = None
    ) -> list[FeedbackItem]:
        if not await self._allowed(viewer, FEEDBACK_READ):
            raise Forbidden("You cannot read feedback.")
        stmt = select(FeedbackItem).order_by(FeedbackItem.created_at.desc()).limit(200)
        if status:
            stmt = stmt.where(FeedbackItem.status == status)
        if kind:
            stmt = stmt.where(FeedbackItem.kind == kind)
        async with self.database.session() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def get(
        self, viewer: Principal, feedback_id: UUID
    ) -> tuple[FeedbackItem, list[FeedbackConversion]]:
        if not await self._allowed(viewer, FEEDBACK_READ):
            raise Forbidden("You cannot read feedback.")
        async with self.database.session() as session:
            item = await session.get(FeedbackItem, feedback_id)
            if item is None:
                raise FeedbackNotFound("This feedback does not exist.")
            conversions = list(
                (
                    await session.execute(
                        select(FeedbackConversion).where(FeedbackConversion.feedback_id == feedback_id)
                    )
                )
                .scalars()
                .all()
            )
        return item, conversions

    async def set_status(self, viewer: Principal, feedback_id: UUID, status: str) -> FeedbackItem:
        if not await self._allowed(viewer, FEEDBACK_READ):
            raise Forbidden("You cannot review feedback.")
        async with self.database.unit_of_work() as uow:
            item = await uow.session.get(FeedbackItem, feedback_id, with_for_update=True)
            if item is None:
                raise FeedbackNotFound("This feedback does not exist.")
            if item.status == "converted":
                raise Conflict("This feedback was already converted.", code="feedback.already_converted")
            item.status, item.updated_at = status, utc_now(self.clock)
            item.reviewed_by = viewer.acting_for or viewer.user_id
            return item
