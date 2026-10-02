"""Built-in Control Center panels (T024, T029). Domain panels (health 025, infrastructure 006, storage, …)
are contributed by their owning modules through the ``admin.panel`` capability; until those modules exist,
their slots render as ``unavailable`` placeholders so the Control Center layout stays stable."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.administration import AUDIT_STATUS_CAPABILITY, PanelResult
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal


class ConfigurationPanel:
    """First real panel: setup completion, active policies, invalid stored values."""

    def __init__(self, first_run: Any, policies: Any, metrics_snapshot: Any) -> None:
        self.first_run = first_run
        self.policies = policies
        self.metrics_snapshot = metrics_snapshot

    async def panel(self, principal: Principal) -> PanelResult:
        invalid = int(self.metrics_snapshot().get("admin.config.invalid_stored_values", 0))
        return PanelResult(
            "partial" if invalid else "available",
            {
                "first_run_completed": await self.first_run.completed(),
                "active_policies": len(await self.policies.active()),
                "invalid_stored_values": invalid,
            },
        )


class PlaceholderPanel:
    """Slot of a domain whose module is not installed yet (health 025, infrastructure 006, storage)."""

    def __init__(self, owner_spec: str) -> None:
        self.owner_spec = owner_spec

    async def panel(self, principal: Principal) -> PanelResult:
        return PanelResult("unavailable", {"reason": "not_installed", "provided_by": self.owner_spec})


class AuditPanel:
    """Audit chain status, fed by the ``audit.status`` capability (spec 021 completion in authz)."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def panel(self, principal: Principal) -> PanelResult:
        providers = self.capabilities.system_providers(AUDIT_STATUS_CAPABILITY)
        if not providers:
            return PanelResult("unavailable", {"reason": "not_installed"})
        status: Mapping[str, Any] = await providers[0].provider.status()
        return PanelResult("available" if status.get("verified", True) else "partial", dict(status))
