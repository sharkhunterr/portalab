"""Issue 363: the requests' notifications through ``notifications.send`` — a new request to the members who
handle them, and each change of a request to every member who wants it (accepted, in progress, refused and
why, there: its page). Never blocking."""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from portalab.capabilities.media_core import LibraryTitle
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users, WithPermission
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.logging import get_logger
from portalab.modules.requests.permissions import MANAGE

log = get_logger("portalab.requests")
UPDATES = "requests.updates"
QUEUE = "requests.queue"


class RequestsNotifier:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def _send(self, request: CommunicationRequest) -> None:
        try:
            providers = self.capabilities.system_providers(NOTIFY)
            if providers:
                await asyncio.wait_for(providers[0].provider.send(request), timeout=10)
        except Exception as exc:
            log.warning("request notification failed", extra={"fields": {"error": type(exc).__name__}})

    async def queue(self, request_id: UUID, kind: str, title: str) -> None:
        await self._send(
            CommunicationRequest(
                category=QUEUE,
                template_key="media:ask.notify.new",
                audience=WithPermission(MANAGE),
                dedup_key=f"request:{request_id}:new",
                params={"title": title[:120], "kind": kind},
                subject_ref=f"request:{request_id}",
                required_permission=MANAGE,
                action_url="/admin/requests",
            )
        )

    async def status(self, users: Sequence[UUID], row: Any, there: LibraryTitle | None) -> None:
        if not users:
            return
        params: dict[str, Any] = {"title": str(row.title)[:120], "kind": row.kind}
        if row.reason:
            params["reason"] = str(row.reason)[:200]
        await self._send(
            CommunicationRequest(
                category=UPDATES,
                template_key=f"media:ask.notify.{'reopened' if row.status == 'new' else row.status}",
                audience=Users(tuple(users)),
                dedup_key=f"request:{row.id}:{row.status}:{row.updated_at.isoformat()}",
                params=params,
                subject_ref=f"request:{row.id}",
                action_url=f"/media/{there.object_id}" if there is not None else "/requests",
            )
        )
