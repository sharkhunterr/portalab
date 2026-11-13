"""Feedback (T030; R10): admin-defined forms (seeded ``general``, ``bug_report``, ``feature_request``) with
validated structured fields; a submission is a ``feedback_item`` — **never** a ticket by itself. Staff with
``feedback.read`` review or dismiss; form versions are pinned on each item.

027: a form may be **requested** from members between two dates — it shows as « your opinion is asked »
and takes one answer per member (``feedback.submitted`` with ``target = request``, rewardable); staff may
**reply** to a feedback (shown in the member's list) and read a request's **results** (counts, average
ratings, choices, latest comments)."""

from collections import Counter
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.notifications.layout import excerpt
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.support.admin.definitions import Definitions
from portalab.modules.support.models import FeedbackConversion, FeedbackEvent, FeedbackForm, FeedbackItem
from portalab.modules.support.workflow.types import parse_fields, validate_values

FEEDBACK_SUBMIT = "feedback.submit"
FEEDBACK_READ = "feedback.read"


def record(
    session: Any,
    feedback_id: UUID,
    kind: str,
    actor: Principal | None,
    at: datetime,
    *,
    text: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """027: one line of a feedback's history (written in the caller's unit of work)."""
    session.add(
        FeedbackEvent(
            feedback_id=feedback_id,
            kind=kind,
            text=text,
            detail=detail or {},
            actor_id=(actor.acting_for or actor.user_id) if actor else None,
            at=at,
        )
    )


class FeedbackNotFound(NotFound):
    default_code = "feedback.not_found"
    default_title = "Feedback not found"


class RequestClosed(Conflict):
    default_code = "feedback.request_closed"
    default_title = "This request is closed"


class AlreadyAnswered(Conflict):
    default_code = "feedback.already_answered"
    default_title = "Already answered"


def is_open(form: FeedbackForm, at: datetime) -> bool:
    return (
        form.enabled
        and form.requested
        and (form.opens_at is None or form.opens_at <= at)
        and (form.closes_at is None or at < form.closes_at)
    )


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
        self.notifier: Any = None  # 027: tells the member a reply arrived (``SupportNotifier``)

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
        user = principal.acting_for or principal.user_id
        if form.requested:
            if not is_open(form, now):
                raise RequestClosed("This request is not open.")
            async with self.database.session() as session:
                answered = await session.scalar(
                    select(FeedbackItem.id).where(
                        FeedbackItem.form_key == form.key, FeedbackItem.submitter_id == user
                    )
                )
            if answered is not None:
                raise AlreadyAnswered("You already answered this request.")
        async with self.database.unit_of_work() as uow:
            item = FeedbackItem(
                form_key=form.key,
                form_version=form.version,
                kind=form.kind,
                submitter_id=user,
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
                {
                    "feedback": str(item.id),
                    "kind": item.kind,
                    "target": "request" if form.requested else "submitted",
                },
                occurred_at=now,
                actor=principal,
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
            now = utc_now(self.clock)
            kind = "closed" if status == "dismissed" else "reopened" if item.status == "dismissed" else "read"
            if item.status != status:
                record(uow.session, item.id, kind, viewer, now)
            item.status, item.updated_at = status, now
            item.reviewed_by = viewer.acting_for or viewer.user_id
            return item

    # --- 027: requests, the member's own feedback, replies and results ---------------------------------
    async def open_requests(self, principal: Principal) -> list[tuple[FeedbackForm, bool]]:
        """Requests open now, each with whether the member already answered."""
        user = principal.acting_for or principal.user_id
        now = utc_now(self.clock)
        forms = [f for f in await self.definitions.forms() if is_open(f, now)]
        if not forms:
            return []
        async with self.database.session() as session:
            answered = set(
                (
                    await session.execute(
                        select(FeedbackItem.form_key).where(
                            FeedbackItem.submitter_id == user,
                            FeedbackItem.form_key.in_([f.key for f in forms]),
                        )
                    )
                ).scalars()
            )
        return [(f, f.key in answered) for f in forms]

    async def mine(self, principal: Principal) -> list[FeedbackItem]:
        user = principal.acting_for or principal.user_id
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(FeedbackItem)
                        .where(FeedbackItem.submitter_id == user)
                        .order_by(FeedbackItem.created_at.desc())
                        .limit(50)
                    )
                )
                .scalars()
                .all()
            )

    async def history(self, viewer: Principal, feedback_id: UUID) -> list[FeedbackEvent]:
        if not await self._allowed(viewer, FEEDBACK_READ):
            raise Forbidden("You cannot review feedback.")
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(FeedbackEvent)
                        .where(FeedbackEvent.feedback_id == feedback_id)
                        .order_by(FeedbackEvent.at, FeedbackEvent.id)
                    )
                ).scalars()
            )

    async def rewards(self, ids: list[UUID]) -> dict[UUID, list[str]]:
        """027: the rewards given for these feedback, in order (their labels)."""
        if not ids:
            return {}
        out: dict[UUID, list[str]] = {}
        async with self.database.session() as session:
            rows = await session.execute(
                select(FeedbackEvent.feedback_id, FeedbackEvent.detail)
                .where(FeedbackEvent.feedback_id.in_(ids), FeedbackEvent.kind == "rewarded")
                .order_by(FeedbackEvent.at)
            )
            for feedback_id, detail in rows:
                label = str((detail or {}).get("label") or "").strip()
                if label:
                    out.setdefault(feedback_id, []).append(label)
        return out

    async def rewarded(self, viewer: Principal, feedback_id: UUID, detail: dict[str, Any]) -> None:
        """027: a reward given for this feedback (through the economy's or the shop's own grants), kept in
        its history."""
        if not await self._allowed(viewer, FEEDBACK_READ):
            raise Forbidden("You cannot review feedback.")
        async with self.database.unit_of_work() as uow:
            item = await uow.session.get(FeedbackItem, feedback_id)
            if item is None:
                raise FeedbackNotFound("This feedback does not exist.")
            now = utc_now(self.clock)
            record(uow.session, feedback_id, "rewarded", viewer, now, detail=detail)
            member = item.submitter_id
        if self.notifier is not None and member is not None:  # told even when no word goes with it
            await self.notifier.send(
                "support.feedback",
                "support:notify.feedbackReward",
                member,
                f"feedback.reward:{feedback_id}:{int(now.timestamp())}",
                # issue 398: the amount shows as the interface's reward chip
                {
                    "what": str(detail.get("label") or ""),
                    "value": str(detail.get("value") or ""),
                    "amount": int(detail.get("amount") or 0),
                },
                "/feedback",
            )

    async def reply(
        self, viewer: Principal, feedback_id: UUID, text: str, *, append: bool = False
    ) -> FeedbackItem:
        """``append``: the new words follow the earlier reply (the member keeps the whole exchange); the
        history keeps each reply in its own words."""
        if not await self._allowed(viewer, FEEDBACK_READ):
            raise Forbidden("You cannot review feedback.")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            item = await uow.session.get(FeedbackItem, feedback_id, with_for_update=True)
            if item is None:
                raise FeedbackNotFound("This feedback does not exist.")
            words = text.strip()
            item.reply = f"{item.reply}\n\n{words}" if append and item.reply else words
            item.replied_at, item.updated_at = now, now
            record(uow.session, item.id, "replied", viewer, now, text=words)
            if item.status == "new":
                item.status = "reviewed"
            item.reviewed_by = viewer.acting_for or viewer.user_id
            await self.events.publish(
                uow.session,
                "feedback.replied",
                {"feedback": str(item.id), "kind": item.kind, "target": "reply"},
                occurred_at=now,
                actor=viewer,
                source="support",
                dedup_key=f"feedback.replied:{item.id}:{int(now.timestamp())}",
            )
        if self.notifier is not None:
            await self.notifier.send(
                "support.feedback",
                "support:notify.feedbackReply",
                item.submitter_id,
                f"feedback.reply:{item.id}:{int(now.timestamp())}",
                {"quote": excerpt(words)},  # issue 398: what the team answered
                "/feedback",
            )
        return item

    async def results(self, viewer: Principal, form_key: str) -> dict[str, Any]:
        """A form's answers summed up: count, then per field — average and spread of ratings, counts of
        choices and yes/no, the latest texts."""
        if not await self._allowed(viewer, FEEDBACK_READ):
            raise Forbidden("You cannot read feedback.")
        async with self.database.session() as session:
            form = await session.get(FeedbackForm, form_key)
            if form is None:
                raise FeedbackNotFound("This form does not exist.")
            total = int(
                await session.scalar(
                    select(func.count()).select_from(FeedbackItem).where(FeedbackItem.form_key == form_key)
                )
                or 0
            )
            rows = (
                (
                    await session.execute(
                        select(FeedbackItem.payload)
                        .where(FeedbackItem.form_key == form_key)
                        .order_by(FeedbackItem.created_at.desc())
                        .limit(500)
                    )
                )
                .scalars()
                .all()
            )
        fields: list[dict[str, Any]] = []
        for field in parse_fields(form.fields):
            values = [row.get(field.key) for row in rows if row.get(field.key) not in (None, "", [])]
            entry: dict[str, Any] = {"key": field.key, "label": field.label, "type": field.type}
            entry["answers"] = len(values)
            if field.type in ("rating", "number"):
                numbers = [float(v) for v in values if isinstance(v, int | float)]
                entry["average"] = round(sum(numbers) / len(numbers), 2) if numbers else None
                if field.type == "rating":
                    spread = Counter(int(v) for v in numbers)
                    entry["counts"] = {str(star): spread.get(star, 0) for star in range(1, 6)}
            elif field.type in ("select", "multi_select", "boolean"):
                counter: Counter[str] = Counter()
                for value in values:
                    for one in value if isinstance(value, list) else [value]:
                        counter[str(one).lower() if isinstance(one, bool) else str(one)] += 1
                entry["counts"] = dict(counter.most_common())
            else:
                entry["latest"] = [str(v)[:500] for v in values[:20]]
            fields.append(entry)
        return {"form": form.key, "label": form.label, "total": total, "fields": fields}
