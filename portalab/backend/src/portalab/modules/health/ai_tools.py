"""The assistant's maintenance tool (issue 171): ``maintenance.windows`` — the maintenance under way and the
one planned (which service, or the whole portal; when it starts and ends; what it is about), so « why is
Plex down? » or « is anything planned tonight? » is answered from the portal's own schedule."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.ai import AITool, AIToolRegistry, SourceRef, ToolResult
from portalab.capabilities.health import SERVICE_DIRECTORY
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.health.permissions import SERVICES_READ

OWNER = "module:health"
MAX_WINDOWS = 10


class HealthAiTools:
    def __init__(self, module: Any, clock: Clock | None = None) -> None:
        self.module = module
        self.clock = clock

    async def _names(self) -> dict[str, str]:
        try:
            providers = self.module.capabilities.system_providers(SERVICE_DIRECTORY)
            return {s.id: s.name for s in await providers[0].provider.services()} if providers else {}
        except Exception:
            return {}

    async def windows(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        names = await self._names()
        wanted = str(params.get("service") or "").strip().casefold()  # issue 171: one service (« Plex »)
        rows = [
            row
            for row in await self.module.maintenance.windows()
            if not wanted
            or row["service_id"] is None  # the whole portal's concerns every service
            or wanted in names.get(row["service_id"], "").casefold()
        ][:MAX_WINDOWS]
        items = [
            {
                "title": row["title"],
                "status": row["status"],  # scheduled | active
                "service": names.get(row["service_id"], row["service_id"])
                if row["service_id"]
                else "the whole portal",
                "starts_at": row["starts_at"],
                "ends_at": row["ends_at"],
                "about": str(row.get("description") or "")[:300] or None,
            }
            for row in rows
        ]
        active = [i for i in items if i["status"] == "active"]
        summary = (
            f"{len(active)} maintenance(s) under way. " if active else "No maintenance under way. "
        ) + (f"{len(items) - len(active)} planned." if len(items) > len(active) else "None planned.")
        now = utc_now(self.clock)
        sources = [
            SourceRef("maintenance", f"maintenance:{row['id']}", row["title"], "real", now, "/services")
            for row in rows
        ]
        return ToolResult("ok", {"summary": summary, "windows": items}, sources)

    def tools(self) -> list[AITool]:
        return [
            AITool(
                "maintenance.windows",
                "The maintenance under way and planned: which service (or the whole portal), when it starts "
                "and ends, what it is about; optionally for one service.",
                {
                    "type": "object",
                    "properties": {"service": {"type": "string", "maxLength": 100}},
                    "additionalProperties": False,
                },
                SERVICES_READ,
                "read",
                self.windows,
                owner=OWNER,
            )
        ]

    def register(self, registry: AIToolRegistry) -> None:
        for tool in self.tools():
            if registry.get(tool.name) is None:
                registry.register(tool)
