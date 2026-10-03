"""First-party feature lifecycle (T029; R15, FR-004): every module has a descriptor (``requires``) and an
enabled state kept in the 020 toggles. Disabling a module refuses while enabled modules depend on it
(unless the Admin confirms the cascade) and removes its contributions through the same registry sweep
as plugins; re-enabling registers them again at the next restart. The registry also answers 020's
``ToggleHook`` before enabling a module or a plugin (dependencies first)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from portalab.capabilities.plugins import TOGGLE_WRITER
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, NotFound, Unavailable


@dataclass(frozen=True, slots=True)
class ModuleDescriptor:
    key: str
    requires: tuple[str, ...] = ()
    provides: tuple[str, ...] = field(default_factory=tuple)
    essential: bool = False  # the kernel: never disabled


MODULES: tuple[ModuleDescriptor, ...] = (
    ModuleDescriptor("identity", essential=True),
    ModuleDescriptor("authz", essential=True),
    ModuleDescriptor("privacy", essential=True),
    ModuleDescriptor("administration", essential=True),
    ModuleDescriptor("events", essential=True),
    ModuleDescriptor("shell", essential=True),
    ModuleDescriptor("ui", essential=True),
    ModuleDescriptor("i18n", essential=True),
    ModuleDescriptor("plugins", essential=True),
    ModuleDescriptor("connectors"),
    ModuleDescriptor("health", ("connectors",)),
    ModuleDescriptor("observability"),
    ModuleDescriptor("search"),
    ModuleDescriptor("dashboard"),
    ModuleDescriptor("notifications"),
    ModuleDescriptor("statistics", ("events",)),
    ModuleDescriptor("media", ("connectors",)),
    ModuleDescriptor("content"),
    ModuleDescriptor("wiki", ("content",)),
    ModuleDescriptor("news", ("content",)),
    ModuleDescriptor("calendar", ("content",)),
    ModuleDescriptor("support", ("notifications",)),
    ModuleDescriptor("ai"),
    ModuleDescriptor("gamification", ("events",)),
    ModuleDescriptor("campaigns", ("gamification",)),
    ModuleDescriptor("automations", ("events",)),
    ModuleDescriptor("community", ("gamification",)),
    ModuleDescriptor("marketplace", ("gamification",)),
)


class ModuleRegistry:
    def __init__(
        self,
        capabilities: CapabilityRegistry,
        remove: Callable[[str], Awaitable[dict[str, int]]],
        plugin_problems: Callable[[str], Awaitable[list[str]]],
        descriptors: tuple[ModuleDescriptor, ...] = MODULES,
    ) -> None:
        self.capabilities = capabilities
        self.remove = remove
        self.plugin_problems = plugin_problems
        self.descriptors = {d.key: d for d in descriptors}
        self.restart_needed: set[str] = set()

    def _writer(self) -> Any:
        providers = self.capabilities.system_providers(TOGGLE_WRITER)
        if not providers:
            raise Unavailable("Module toggles are not available.", code="admin.unavailable")
        return providers[0].provider

    async def states(self) -> list[dict[str, Any]]:
        writer = self._writer()
        out = []
        for descriptor in self.descriptors.values():
            enabled = await writer.is_enabled("module", descriptor.key)
            out.append(
                {
                    "key": descriptor.key,
                    "enabled": enabled,
                    "requires": list(descriptor.requires),
                    "essential": descriptor.essential,
                    "needs_restart": descriptor.key in self.restart_needed,
                }
            )
        return out

    async def _enabled(self) -> set[str]:
        writer = self._writer()
        return {k for k in self.descriptors if await writer.is_enabled("module", k)}

    def dependents(self, key: str, enabled: set[str]) -> list[str]:
        direct = [d.key for d in self.descriptors.values() if key in d.requires and d.key in enabled]
        out: list[str] = []
        for dependent in direct:
            for nested in self.dependents(dependent, enabled):
                if nested not in out:
                    out.append(nested)
            if dependent not in out:
                out.append(dependent)
        return out

    async def set(self, actor: Principal, key: str, enabled: bool, *, cascade: bool = False) -> list[str]:
        descriptor = self.descriptors.get(key)
        if descriptor is None:
            raise NotFound("Unknown module.", code="admin.unknown_module")
        writer = self._writer()
        if enabled:
            await writer.set(actor, "module", key, True, "enabled from the module manager")
            self.restart_needed.add(key)
            return [key]
        if descriptor.essential:
            raise Conflict("This module is part of the kernel.", code="plugin.essential_module")
        chain = self.dependents(key, await self._enabled())
        if chain and not cascade:
            raise Conflict(
                "Other enabled modules need this one.",
                code="plugin.has_dependents",
                extensions={"dependents": chain},
            )
        for module in [*chain, key]:
            await writer.set(actor, "module", module, False, "disabled from the module manager")
            await self.remove(f"module:{module}")
            self.restart_needed.discard(module)
        return [*chain, key]

    # --- 020 ToggleHook -------------------------------------------------------------------------------
    async def check_enable(self, kind: str, ref: str) -> list[str]:
        if kind == "module":
            descriptor = self.descriptors.get(ref)
            if descriptor is None:
                return []
            enabled = await self._enabled()
            return [f"module {ref} needs {r}" for r in descriptor.requires if r not in enabled]
        if kind == "plugin":
            return await self.plugin_problems(ref)
        return []
