"""Incident notifications (T012): fan-out through the ``notifications.send`` port (Notifications 010) to the
users permitted on the affected services; critical incidents are urgent (alert channel). Without the port
(until 010) nothing is sent — never an error. Category ``support.incident``."""

import asyncio
from typing import Any

from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, WithPermission
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.support.incidents.service import Change
from portalab.modules.support.observability import log
from portalab.modules.support.permissions import INCIDENTS_READ

CATEGORY = "support.incident"


class IncidentNotifier:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities
        self._pending: set[asyncio.Task[None]] = set()

    def _port(self) -> Any | None:
        try:
            providers = self.capabilities.system_providers(NOTIFY)
        except Exception:
            return None
        return providers[0].provider if providers else None

    def __call__(self, change: Change) -> None:
        port = self._port()
        if port is None:
            return
        task = asyncio.ensure_future(self._send(port, change))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _send(self, port: Any, change: Change) -> None:
        critical = change.severity == "critical" and change.kind != "resolved"
        try:
            await port.send(
                CommunicationRequest(
                    category=CATEGORY,
                    template_key=f"support:incident.{change.kind}",
                    audience=WithPermission(INCIDENTS_READ, change.service_ids),
                    # issue 398: every update is told (its version), not only the first of each severity
                    dedup_key=f"{CATEGORY}:{change.incident_id}:{change.kind}:{change.version}",
                    kind="alert" if critical else "notification",
                    priority="critical" if critical else ("high" if change.severity == "major" else "normal"),
                    params={
                        "number": f"INC-{change.number:04d}",
                        "title": change.title,
                        "severity": change.severity,
                        "state": change.state or "none",
                        "summary": change.summary[:600] or "none",
                        "quote": change.message[:1000],
                        "created_at": change.created_at.isoformat() if change.created_at else "none",
                        "resolved_at": change.resolved_at.isoformat() if change.resolved_at else "none",
                    },
                    source="module",
                    subject_ref=f"incident:{change.incident_id}",
                    required_permission=INCIDENTS_READ,
                    action_url=f"/incidents/{change.incident_id}",
                )
            )
        except Exception:
            log.warning("incident notification not sent", extra={"incident": str(change.incident_id)})

    async def drain(self) -> None:
        while self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)
