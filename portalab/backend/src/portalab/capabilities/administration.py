"""Administration contribution points (spec 020): first-run steps, Control Center panels and required
actions, admin surfaces, extension toggles hooks. Owner-tagged so a disabled plugin's contributions vanish."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

PANEL_CAPABILITY = "admin.panel"
REQUIRED_ACTION_CAPABILITY = "admin.required_actions"
FIRST_RUN_STEP_CAPABILITY = "admin.first_run_step"
BOOTSTRAP_CAPABILITY = "identity.bootstrap"
PLUGIN_PERMISSIONS_CAPABILITY = "authz.plugin_permissions"
TOGGLE_HOOK_CAPABILITY = "admin.toggle_hook"
AUDIT_STATUS_CAPABILITY = "audit.status"
EXTENSION_STATE_CAPABILITY = "admin.extension_state"
CONFIG_WRITER_CAPABILITY = "admin.config_writer"

PanelState = Literal["available", "partial", "stale", "unavailable", "no-data"]


@dataclass(frozen=True, slots=True)
class PanelResult:
    state: PanelState
    data: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class PanelProvider(Protocol):
    """Registration metadata: ``{"panel": "<id>", "permission": "<key>", "order": int}``."""

    async def panel(self, principal: Principal) -> PanelResult: ...


@dataclass(frozen=True, slots=True)
class RequiredAction:
    id: str
    title_key: str
    impact: int  # higher = broader impact
    criticality: int  # higher = more critical
    since: datetime
    link: str
    actionable: bool = True


@runtime_checkable
class RequiredActionProvider(Protocol):
    async def items(self, principal: Principal) -> list[RequiredAction]: ...


@runtime_checkable
class FirstRunStep(Protocol):
    """Optional wizard step (e.g. ``services`` from 005); metadata ``{"step": id, "skippable": bool}``."""

    async def run(self, payload: Mapping[str, Any], admin_id: UUID) -> Mapping[str, Any]: ...


@runtime_checkable
class Bootstrapper(Protocol):
    async def create_first_admin(
        self, *, login: str, password: str, display_name: str | None = None, email: str | None = None
    ) -> UUID: ...


@runtime_checkable
class PluginPermissions(Protocol):
    async def set_enabled(self, plugin_id: str, enabled: bool) -> int: ...


@runtime_checkable
class ToggleHook(Protocol):
    """Called before enabling an extension (compatibility/dependency check, spec 023 ``ModuleRegistry``)."""

    async def check_enable(self, kind: str, ref: str) -> list[str]: ...


@runtime_checkable
class AuditStatus(Protocol):
    async def status(self) -> Mapping[str, Any]: ...


@runtime_checkable
class ExtensionState(Protocol):
    """Whether a module/plugin/connector/service is enabled (020 toggles; enabled when never toggled)."""

    async def enabled(self, kind: str, ref: str) -> bool: ...


@runtime_checkable
class ConfigWriter(Protocol):
    """Validated, audited global setting change on behalf of an actor (020 ``ConfigService.apply``)."""

    async def set_global(self, actor: Principal, key: str, value: Any, *, reason: str = "") -> None: ...

    async def set_user(self, actor: Principal, key: str, value: Any) -> None:
        """A user-overridable setting for the acting user themself (validated like any change)."""
        ...


@dataclass(frozen=True, slots=True)
class AdminSurface:
    key: str
    label_key: str
    route: str
    permission: str
    owner: str


class AdminSurfaceRegistry:
    def __init__(self) -> None:
        self._surfaces: dict[str, AdminSurface] = {}

    def register(self, surface: AdminSurface) -> AdminSurface:
        existing = self._surfaces.get(surface.key)
        if existing is not None and existing != surface:
            raise ValueError(f"admin surface {surface.key!r} is already registered")
        self._surfaces[surface.key] = surface
        return surface

    def all(self) -> list[AdminSurface]:
        return [self._surfaces[key] for key in sorted(self._surfaces)]

    def unregister(self, owner: str) -> int:
        doomed = [key for key, surface in self._surfaces.items() if surface.owner == owner]
        for key in doomed:
            del self._surfaces[key]
        return len(doomed)


default_admin_surfaces = AdminSurfaceRegistry()
register_admin_surface: Callable[[AdminSurface], AdminSurface] = default_admin_surfaces.register

DynamicValidator = Callable[[Any], Awaitable[list[str]]]


def _spec(name: str, protocol: type[Any], multi: bool, description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=multi, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(PANEL_CAPABILITY, PanelProvider, True, "Control Center panel"),
    _spec(REQUIRED_ACTION_CAPABILITY, RequiredActionProvider, True, "Control Center required actions"),
    _spec(FIRST_RUN_STEP_CAPABILITY, FirstRunStep, True, "Optional first-run wizard step"),
    _spec(BOOTSTRAP_CAPABILITY, Bootstrapper, False, "Creation of the sole first Admin (spec 002)"),
    _spec(PLUGIN_PERMISSIONS_CAPABILITY, PluginPermissions, False, "Enable/withdraw a plugin's permissions"),
    _spec(TOGGLE_HOOK_CAPABILITY, ToggleHook, True, "Compatibility check before enabling an extension"),
    _spec(AUDIT_STATUS_CAPABILITY, AuditStatus, False, "Audit chain status for the Control Center"),
    _spec(EXTENSION_STATE_CAPABILITY, ExtensionState, False, "Enablement of modules/plugins (020 toggles)"),
    _spec(CONFIG_WRITER_CAPABILITY, ConfigWriter, False, "Audited global setting changes (020)"),
)
