"""Ticket notifications (T035; R14) through ``notifications.send`` (010): assignment, status changes and
staff replies to the requester, requester replies to the assignee, feedback outcome. Never blocking."""

import asyncio
from typing import Any
from uuid import UUID

from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.logging import get_logger

log = get_logger("portalab.support")
ASSIGNMENT = "support.assignment"
STATUS = "support.ticket_status"
FEEDBACK = "support.feedback"


class SupportNotifier:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def send(
        self, category: str, template: str, user: UUID | None, dedup: str, params: dict[str, Any], url: str
    ) -> None:
        if user is None:
            return
        try:
            providers = self.capabilities.system_providers(NOTIFY)
        except Exception:
            return
        if not providers:
            return
        try:
            await asyncio.wait_for(
                providers[0].provider.send(
                    CommunicationRequest(
                        category=category,
                        template_key=template,
                        audience=Users((user,)),
                        dedup_key=dedup,
                        params=params,
                        source="module",
                        subject_ref=url.replace("/", ":").strip(":"),
                        action_url=url,
                    )
                ),
                timeout=10,
            )
        except Exception:
            log.warning("support notification not sent")
