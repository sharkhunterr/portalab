"""Observability contracts (spec 025): the common contribution model ``declare_observable`` used by core
modules, plugins and connectors (R11, FR-034), checks on the two health axes (R1), diagnostic action
descriptors (R10), the metadata-only AI reporting API (R9, FR-011/012) and the ports Observability uses
(``notifications.send_alert`` from 010, automation and plugin status from 019/023 — empty until then).

Checks are evaluated by the Observability module; a check that raises or times out yields ``unknown``,
never a green state. Contributions are owner-tagged so a disabled plugin's components disappear (F20).
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.metrics import MetricsRegistry, default_metrics

TechnicalState = Literal["ok", "degraded", "down", "unknown"]
FunctionalState = Literal["ok", "degraded", "failing", "unknown"]
CheckState = Literal["ok", "degraded", "down", "failing", "unknown"]

OBSERVABILITY_HEALTH = "observability.health"
SEND_ALERT = "notifications.send_alert"
AUTOMATION_STATUS = "automations.status"
PLUGIN_STATUS = "plugins.status"


@dataclass(frozen=True, slots=True)
class CheckResult:
    state: CheckState
    reason: str = ""
    facts: Mapping[str, Any] = field(default_factory=dict)  # ids and numbers only, never content


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    evaluate: Callable[[], Awaitable[CheckResult]] = field(compare=False)


@dataclass(frozen=True, slots=True)
class DiagnosticAction:
    """A pointer to an owner's API: Observability lists it, the owner executes and audits it."""

    key: str
    label: str
    method: str
    path: str
    permission: str
    sensitive: bool = False


@dataclass(frozen=True, slots=True)
class ObservedComponent:
    name: str  # e.g. "events", "sync:<service>", "plugin:<id>", "ai"
    owner: str  # "module:<id>" | "plugin:<key>" | "connector:<key>"
    kind: str = "module"
    label: str = ""
    technical_checks: tuple[Check, ...] = ()
    functional_checks: tuple[Check, ...] = ()
    diagnostics: tuple[DiagnosticAction, ...] = ()
    metrics: tuple[str, ...] = ()
    impact: int = 1  # how much of the portal depends on it (ranking)
    criticality: int = 1


ComponentSource = Callable[[], Awaitable[Sequence[ObservedComponent]]]


class ObservableRegistry:
    """Static components plus dynamic sources (e.g. one component per configured service)."""

    def __init__(self) -> None:
        self._components: dict[str, ObservedComponent] = {}
        self._sources: dict[str, tuple[ComponentSource, str]] = {}

    def declare(self, component: ObservedComponent) -> ObservedComponent:
        existing = self._components.get(component.name)
        if existing is not None and existing.owner != component.owner:
            raise ValueError(f"component {component.name!r} is already declared by {existing.owner}")
        self._components[component.name] = component
        return component

    def declare_source(self, name: str, source: ComponentSource, *, owner: str) -> None:
        self._sources[name] = (source, owner)

    async def components(self) -> list[ObservedComponent]:
        found = dict(self._components)
        for source, _ in self._sources.values():
            try:
                for component in await source():
                    found.setdefault(component.name, component)
            except Exception:  # noqa: S112 — a failing source never hides the others
                continue
        return [found[name] for name in sorted(found)]

    def unregister(self, owner: str) -> int:
        doomed = [n for n, c in self._components.items() if c.owner == owner]
        sources = [n for n, (_, who) in self._sources.items() if who == owner]
        for name in doomed:
            del self._components[name]
        for name in sources:
            del self._sources[name]
        return len(doomed) + len(sources)


default_observables = ObservableRegistry()


def declare_observable(
    name: str,
    *,
    owner: str,
    kind: str = "module",
    label: str = "",
    technical_checks: Sequence[Check] = (),
    functional_checks: Sequence[Check] = (),
    diagnostics: Sequence[DiagnosticAction] = (),
    metrics: Sequence[str] = (),
    impact: int = 1,
    criticality: int = 1,
    registry: ObservableRegistry = default_observables,
) -> ObservedComponent:
    return registry.declare(
        ObservedComponent(
            name,
            owner,
            kind,
            label or name,
            tuple(technical_checks),
            tuple(functional_checks),
            tuple(diagnostics),
            tuple(metrics),
            impact,
            criticality,
        )
    )


# --- AI: metadata only (FR-011/012) ---------------------------------------------------------------------
AiOutcome = Literal["ok", "error", "timeout", "refused"]


def report_ai_call(
    *,
    provider: str,
    model: str,
    latency_ms: float,
    outcome: AiOutcome,
    tools: Sequence[str] = (),
    actions: int = 0,
    registry: MetricsRegistry = default_metrics,
) -> None:
    """The only AI reporting API: counts, latency, outcome, provider/model and tool names. It has no
    parameter for prompts, responses or conversation content, so none can reach observability storage."""
    labels = {"provider": provider[:64], "model": model[:64], "outcome": outcome}
    registry.counter("ai", "ai.requests", labels=labels)
    registry.histogram("ai", "ai.latency", latency_ms, {"provider": provider[:64], "model": model[:64]})
    for tool in tools[:16]:
        registry.counter("ai", "ai.tool_calls", labels={"tool": tool[:64]})
    if actions:
        registry.counter("ai", "ai.actions", actions, {"provider": provider[:64]})


# --- ports ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Alert:
    key: str
    title: str
    severity: Literal["info", "warning", "critical"]
    component: str
    raised_at: datetime
    facts: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class AlertSender(Protocol):
    async def send_alert(self, alert: Alert) -> None: ...


@dataclass(frozen=True, slots=True)
class AutomationStatus:
    active_rules: int
    executions: int
    failures: int
    suspended: Sequence[Mapping[str, str]] = ()  # [{"rule_id", "reason"}] — e.g. loop protection


@runtime_checkable
class AutomationStatusReader(Protocol):
    async def status(self) -> AutomationStatus: ...


@dataclass(frozen=True, slots=True)
class PluginStatus:
    plugin_id: str
    state: Literal["active", "disabled", "error", "incompatible", "invalid_config", "missing_dependency"]
    version: str
    last_activity_at: datetime | None = None
    recent_errors: int = 0
    detail: str = ""


@runtime_checkable
class PluginStatusReader(Protocol):
    async def plugins(self) -> list[PluginStatus]: ...


@runtime_checkable
class ObservabilityHealth(Protocol):
    async def component_health(self, component: str) -> Mapping[str, Any] | None: ...

    async def problems(self, limit: int = 20) -> list[Mapping[str, Any]]: ...


def _spec(name: str, protocol: type[Any], description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=False, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(OBSERVABILITY_HEALTH, ObservabilityHealth, "Portal component health and ranked problems (025)"),
    _spec(SEND_ALERT, AlertSender, "Alert delivery (Notifications 010)"),
    _spec(AUTOMATION_STATUS, AutomationStatusReader, "Automation engine status (019)"),
    _spec(PLUGIN_STATUS, PluginStatusReader, "Plugin states (023)"),
)
