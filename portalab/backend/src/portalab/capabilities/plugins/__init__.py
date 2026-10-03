"""Extensibility contracts (spec 023, contracts/extensibility-contracts.md).

* ``plugins.extension_activation`` — per-user activation of a plugin acquired in the Marketplace (015):
  grants ``plugin:<key>.use`` through 003 and reports ``active|needs_configuration|failed|incompatible``;
* ports through which the plugin manager reaches registries owned by modules (the manager never imports
  another module): ``i18n.plugin_catalogs`` (026), ``ui.theme_registry`` (022) and ``admin.toggle_writer``
  (020 toggles, for first-party module enable/disable).
Everything a plugin contributes is owner-tagged ``plugin:<key>`` and removable with ``unregister(owner)``.
"""

from collections.abc import Mapping
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

EXTENSION_ACTIVATION = "plugins.extension_activation"
I18N_CATALOGS = "i18n.plugin_catalogs"
THEME_REGISTRY = "ui.theme_registry"
TOGGLE_WRITER = "admin.toggle_writer"

ActivationStatus = Literal["active", "needs_configuration", "failed", "incompatible"]


@runtime_checkable
class ExtensionActivation(Protocol):
    async def activate_for_user(self, product_ref: str, user: UUID) -> ActivationStatus: ...

    async def deactivate_for_user(self, product_ref: str, user: UUID) -> None: ...

    async def status(self, product_ref: str, user: UUID) -> ActivationStatus: ...


@runtime_checkable
class PluginCatalogPort(Protocol):
    def register(
        self,
        plugin_id: str,
        bundle: Mapping[str, Mapping[str, Mapping[str, str]]],
        *,
        owner: str | None = None,
    ) -> None: ...

    def unregister(self, owner: str) -> int: ...


@runtime_checkable
class ThemeRegistryPort(Protocol):
    async def register(
        self, actor: Principal, document: Mapping[str, Any], *, source: str = "admin", owner: str = "core"
    ) -> dict[str, Any]: ...

    async def update(
        self,
        actor: Principal,
        key: str,
        *,
        definition: Mapping[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]: ...

    async def unregister(self, owner: str) -> int: ...


@runtime_checkable
class ToggleWriter(Protocol):
    async def is_enabled(self, kind: str, ref: str, *, default: bool = True) -> bool: ...

    async def set(self, actor: Principal, kind: str, ref: str, enabled: bool, reason: str = "") -> Any: ...


def _spec(name: str, protocol: type[Any], description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=False, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(
        EXTENSION_ACTIVATION, ExtensionActivation, "Per-user plugin activation for Marketplace products (023)"
    ),
    _spec(I18N_CATALOGS, PluginCatalogPort, "Plugin message catalogs (026)"),
    _spec(THEME_REGISTRY, ThemeRegistryPort, "Theme registrations by plugins (022)"),
    _spec(TOGGLE_WRITER, ToggleWriter, "Audited extension toggles (020)"),
)
