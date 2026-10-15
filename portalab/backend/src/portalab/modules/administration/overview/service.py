"""Control Center aggregation (T024; R6/R7, FR-001..004): every panel is loaded independently within its time
budget; a slow or failing provider yields ``unavailable`` for that panel only. Panels and required actions are
filtered by the viewer's permissions; required actions are sorted actionable → impact → criticality → age."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from portalab.capabilities.administration import (
    PANEL_CAPABILITY,
    REQUIRED_ACTION_CAPABILITY,
    PanelResult,
    RequiredAction,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.administration.observability import log, metrics


@dataclass(frozen=True, slots=True)
class PanelView:
    panel: str
    state: str
    data: dict[str, Any]


class ControlCenter:
    def __init__(
        self, capabilities: CapabilityRegistry, authorizer: Authorizer, *, timeout_ms: int = 1500
    ) -> None:
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.timeout = timeout_ms / 1000

    async def _allowed(self, principal: Principal, permission: str | None) -> bool:
        return permission is None or await self.authorizer.is_allowed(principal, permission)

    async def _panel(self, registration: Any, principal: Principal) -> PanelView:
        name = str(registration.metadata.get("panel", registration.instance_ref))
        started = time.perf_counter()
        try:
            result: PanelResult = await asyncio.wait_for(registration.provider.panel(principal), self.timeout)
            view = PanelView(name, result.state, dict(result.data))
        except Exception as exc:
            metrics.increment(f"admin.panels.{name.replace('-', '_').replace('.', '_')}.failed")
            log.warning("panel unavailable", extra={"fields": {"panel": name, "error": type(exc).__name__}})
            view = PanelView(name, "unavailable", {})
        metrics.timing(
            f"admin.panels.{name.replace('-', '_').replace('.', '_')}.ms",
            (time.perf_counter() - started) * 1000,
        )
        return view

    async def overview(self, principal: Principal) -> tuple[list[PanelView], list[RequiredAction]]:
        registrations = [
            registration
            for registration in self.capabilities.system_providers(PANEL_CAPABILITY)
            if await self._allowed(principal, registration.metadata.get("permission"))
        ]
        registrations.sort(key=lambda reg: (int(reg.metadata.get("order", 100)), reg.instance_ref))
        panels = list(await asyncio.gather(*(self._panel(reg, principal) for reg in registrations)))
        actions: list[RequiredAction] = []
        for registration in self.capabilities.system_providers(REQUIRED_ACTION_CAPABILITY):
            # issue 134: what the administration must do is the administrators' — a provider saying no
            # permission shows nothing (closed by default), never everything to everyone
            permission = registration.metadata.get("permission")
            if permission is None or not await self._allowed(principal, permission):
                continue
            try:
                actions.extend(await asyncio.wait_for(registration.provider.items(principal), self.timeout))
            except Exception:
                metrics.increment("admin.required_actions.failed")
        actions.sort(key=lambda a: (not a.actionable, -a.impact, -a.criticality, a.since))
        return panels, actions
