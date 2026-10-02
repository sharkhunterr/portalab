"""Optional, skippable ``services`` step of the Admin first-run wizard (T037; 020 ``FirstRunStep``).

Decided 2026-10-01: Admin wizard only (not user onboarding). With no payload it lists the installed
connectors; with ``{"services": [{connector, name, config, secrets}]}`` it configures them — configured,
never enabled (enabling still needs the connection/compatibility check).
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from portalab.core.authz_port import Principal
from portalab.modules.connectors.services.manager import ServiceManager

STEP = "services"


class ServicesFirstRunStep:
    def __init__(self, manager: ServiceManager) -> None:
        self.manager = manager

    async def run(self, payload: Mapping[str, Any], admin_id: UUID) -> Mapping[str, Any]:
        items = list(payload.get("services") or [])
        if not items:
            return {"connectors": [{"key": c["key"], "name": c["name"]} for c in self.manager.catalog()]}
        actor = Principal(user_id=admin_id)
        configured = []
        for item in items:
            service_id = await self.manager.configure(
                actor,
                connector_key=str(item["connector"]),
                name=str(item["name"]),
                config=dict(item.get("config") or {}),
                secrets=dict(item.get("secrets") or {}),
            )
            configured.append(str(service_id))
        return {"configured": configured}
