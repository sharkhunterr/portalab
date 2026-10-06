"""« Since your last visit » for support (027): staff answers on my tickets and replies to my feedback."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from portalab.capabilities.dashboard import ChangeItem
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.modules.support.models import FeedbackItem, Ticket, TicketComment


class SupportChanges:
    kind = "support"

    def __init__(self, database: Database) -> None:
        self.database = database

    async def changes_since(
        self, principal: Principal, since: datetime, limit: int, ctx: LocaleContext
    ) -> Sequence[ChangeItem]:
        user = principal.acting_for or principal.user_id
        if user is None:
            return []
        items: list[ChangeItem] = []
        async with self.database.session() as session:
            answered = (
                await session.execute(
                    select(Ticket.id, Ticket.number, Ticket.title, func.max(TicketComment.created_at))
                    .join(TicketComment, TicketComment.ticket_id == Ticket.id)
                    .where(
                        Ticket.requester_id == user,
                        TicketComment.internal.is_(False),
                        TicketComment.author_id != user,
                        TicketComment.created_at > since,
                    )
                    .group_by(Ticket.id, Ticket.number, Ticket.title)
                    .limit(limit)
                )
            ).all()
            for ticket_id, number, title, at in answered:
                items.append(
                    ChangeItem(
                        kind="support",
                        occurred_at=at,
                        ref=f"/support/tickets/{ticket_id}",
                        title_key="dashboard:summary.ticketAnswer",
                        title_args={"number": f"T-{number:06d}"},
                        detail=title,
                        priority=4,
                    )
                )
            replied = int(
                await session.scalar(
                    select(func.count())
                    .select_from(FeedbackItem)
                    .where(FeedbackItem.submitter_id == user, FeedbackItem.replied_at > since)
                )
                or 0
            )
            if replied:
                at = await session.scalar(
                    select(func.max(FeedbackItem.replied_at)).where(
                        FeedbackItem.submitter_id == user, FeedbackItem.replied_at > since
                    )
                )
                items.append(
                    ChangeItem(
                        kind="feedback",
                        occurred_at=at or since,
                        ref="/feedback",
                        title_key="dashboard:summary.feedbackReplied",
                        title_args={"count": replied},
                        priority=3,
                    )
                )
        return items
