"""#98: the support's badges — the tickets waiting for an answer from the team, the members' feedback not
read yet, the incidents under way — each for those who may handle it."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.support.feedback.service import FEEDBACK_READ
from portalab.modules.support.models import FeedbackItem, Incident, Ticket
from portalab.modules.support.permissions import INCIDENTS_MANAGE
from portalab.modules.support.tickets.service import TICKETS_MANAGE

TICKETS = "support.queue"
FEEDBACK = "support.feedback_review"
INCIDENTS = "support.incident_console"


class SupportAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        queries: dict[str, Any] = {}
        if await self.authorizer.is_allowed(principal, TICKETS_MANAGE):
            # open whatever the workflow calls its states: not resolved, closed, nor waiting for the member
            queries[TICKETS] = select(func.count()).where(
                Ticket.resolved_at.is_(None), Ticket.closed_at.is_(None), Ticket.state != "waiting_user"
            )
        if await self.authorizer.is_allowed(principal, FEEDBACK_READ):
            queries[FEEDBACK] = select(func.count()).where(FeedbackItem.status == "new")
        if await self.authorizer.is_allowed(principal, INCIDENTS_MANAGE):
            queries[INCIDENTS] = select(func.count()).where(Incident.state != "resolved")
        if not queries:
            return {}
        async with self.database.session() as session:
            return {key: int(await session.scalar(query) or 0) for key, query in queries.items()}
