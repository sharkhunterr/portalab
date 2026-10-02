"""Plugin adapter (T018; FR-009, FR-034): every plugin gets a ``plugin:<id>`` component in the common model
(state, version, last activity, recent errors) from the ``plugins.status`` port (023); a plugin's own
``declare_observable`` contributions are evaluated like any other. A failing plugin is isolated: its
component degrades, the portal stays available."""

from collections.abc import Callable, Sequence
from typing import Any

from portalab.capabilities.observability import (
    PLUGIN_STATUS,
    Check,
    CheckResult,
    CheckState,
    ObservedComponent,
    PluginStatus,
)
from portalab.capabilities.registry import CapabilityRegistry

OWNER = "module:observability"
_TECHNICAL: dict[str, CheckState] = {
    "active": "ok",
    "disabled": "ok",
    "error": "down",
    "incompatible": "down",
    "invalid_config": "down",
    "missing_dependency": "down",
}


def plugin_components(capabilities: CapabilityRegistry) -> Callable[[], Any]:
    async def source() -> Sequence[ObservedComponent]:
        providers = capabilities.system_providers(PLUGIN_STATUS)
        if not providers:
            return []
        return [_component(status) for status in await providers[0].provider.plugins()]

    return source


def _component(status: PluginStatus) -> ObservedComponent:
    facts = {
        "state": status.state,
        "version": status.version,
        "last_activity_at": status.last_activity_at.isoformat() if status.last_activity_at else None,
        "recent_errors": status.recent_errors,
    }

    async def state() -> CheckResult:
        return CheckResult(
            _TECHNICAL.get(status.state, "unknown"), f"{status.state}: {status.detail}".strip(": "), facts
        )

    async def errors() -> CheckResult:
        if status.state == "disabled":
            return CheckResult("ok", "disabled", facts)
        if status.recent_errors:
            return CheckResult("degraded", f"{status.recent_errors} recent error(s)", facts)
        return CheckResult("ok", "no recent error", facts)

    return ObservedComponent(
        f"plugin:{status.plugin_id}",
        f"plugin:{status.plugin_id}",
        kind="plugin",
        label=status.plugin_id,
        technical_checks=(Check("state", state),),
        functional_checks=(Check("errors", errors),),
        impact=1,
    )
