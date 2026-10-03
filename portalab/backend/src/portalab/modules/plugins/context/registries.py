"""Every registry a plugin (or a first-party module) can contribute to (R7, R11). Removal is by owner and
total: ``remove(owner)`` calls ``unregister(owner)`` on each of them — and on the module-owned registries
reached through capability ports (i18n catalogs, themes) — so a disabled or quarantined plugin leaves no
slot behind. ``leftovers(owner)`` is the conformance probe: zero everywhere after a removal."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from portalab.capabilities.ai import AIToolRegistry, default_ai_tools
from portalab.capabilities.automation_actions import ActionRegistry, default_actions
from portalab.capabilities.community import SectionRegistry, ShelfRegistry, default_sections, default_shelves
from portalab.capabilities.connector_sdk import ConnectorRegistry, default_connectors
from portalab.capabilities.content import CalendarSourceRegistry, default_calendar_sources
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.marketplace import ProductTypeRegistry, default_product_types
from portalab.capabilities.media_core import MediaTypeRegistry, default_media_types
from portalab.capabilities.navigation.registry import NavigationRegistry, default_navigation
from portalab.capabilities.notifications import CategoryRegistry, default_categories
from portalab.capabilities.observability import ObservableRegistry, default_observables
from portalab.capabilities.plugins import I18N_CATALOGS, THEME_REGISTRY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import SearchRegistry, default_search
from portalab.capabilities.statistics import PackRegistry, default_packs
from portalab.core.config_declaration import SettingCatalog, default_catalog
from portalab.core.permissions import PermissionRegistry, default_permissions
from portalab.modules.plugins.observability import log


class PageRegistry:
    """Declarative plugin pages (rendered by the SPA's page renderer)."""

    def __init__(self) -> None:
        self._pages: dict[tuple[str, str], tuple[str, Any]] = {}

    def register(self, plugin: str, page: Any) -> None:
        self._pages[(plugin, page.key)] = (f"plugin:{plugin}", page)

    def get(self, plugin: str, key: str) -> Any | None:
        entry = self._pages.get((plugin, key))
        return entry[1] if entry else None

    def of(self, plugin: str) -> list[Any]:
        return [page for (p, _), (_, page) in sorted(self._pages.items()) if p == plugin]

    def unregister(self, owner: str) -> int:
        doomed = [k for k, (who, _) in self._pages.items() if who == owner]
        for key in doomed:
            del self._pages[key]
        return len(doomed)


@dataclass(frozen=True, slots=True)
class PluginRoute:
    plugin: str
    method: str
    path: str
    permission: str
    handler: Any = field(compare=False)


class RouteTable:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str, str], PluginRoute] = {}

    def register(self, route: PluginRoute) -> None:
        self._routes[(route.plugin, route.method, route.path)] = route

    def get(self, plugin: str, method: str, path: str) -> PluginRoute | None:
        return self._routes.get((plugin, method, path))

    def unregister(self, owner: str) -> int:
        plugin = owner.removeprefix("plugin:")
        doomed = [k for k in self._routes if k[0] == plugin]
        for key in doomed:
            del self._routes[key]
        return len(doomed)


@dataclass
class Registries:
    capabilities: CapabilityRegistry
    navigation: NavigationRegistry = default_navigation
    widgets: WidgetRegistry = default_widgets
    search: SearchRegistry = default_search
    calendar: CalendarSourceRegistry = default_calendar_sources
    packs: PackRegistry = default_packs
    actions: ActionRegistry = default_actions
    ai_tools: AIToolRegistry = default_ai_tools
    categories: CategoryRegistry = default_categories
    permissions: PermissionRegistry = default_permissions
    settings: SettingCatalog = default_catalog
    event_types: EventTypeRegistry = default_event_types
    consumers: ConsumerRegistry = default_consumers
    product_types: ProductTypeRegistry = default_product_types
    media_types: MediaTypeRegistry = default_media_types
    sections: SectionRegistry = default_sections
    shelves: ShelfRegistry = default_shelves
    connectors: ConnectorRegistry = default_connectors
    observables: ObservableRegistry = default_observables
    pages: PageRegistry = field(default_factory=PageRegistry)
    routes: RouteTable = field(default_factory=RouteTable)

    def _sync_removers(self) -> dict[str, Callable[[str], int]]:
        return {
            "navigation": self.navigation.unregister,
            "widgets": self.widgets.unregister_owner,
            "search": self.search.unregister,
            "calendar": self.calendar.unregister,
            "statistics": self.packs.unregister,
            "automation_actions": self.actions.unregister,
            "ai_tools": self.ai_tools.unregister,
            "notification_categories": self.categories.unregister,
            "permissions": self.permissions.unregister,
            "settings": self.settings.unregister,
            "event_types": self.event_types.unregister,
            "event_consumers": self.consumers.unregister,
            "capabilities": self.capabilities.unregister,
            "product_types": self.product_types.unregister,
            "media_types": self.media_types.unregister,
            "profile_sections": self.sections.unregister,
            "discovery_shelves": self.shelves.unregister,
            "connectors": self.connectors.unregister,
            "observability": self.observables.unregister,
            "pages": self.pages.unregister,
            "routes": self.routes.unregister,
        }

    async def remove(self, owner: str) -> dict[str, int]:
        removed: dict[str, int] = {}
        for name, remover in self._sync_removers().items():
            try:
                removed[name] = int(remover(owner))
            except Exception:
                log.warning("registry removal failed", extra={"fields": {"registry": name}})
                removed[name] = -1
        catalogs = self.capabilities.system_providers(I18N_CATALOGS)
        removed["i18n"] = int(catalogs[0].provider.unregister(owner)) if catalogs else 0
        themes = self.capabilities.system_providers(THEME_REGISTRY)
        removed["themes"] = int(await themes[0].provider.unregister(owner)) if themes else 0
        return removed

    async def leftovers(self, owner: str) -> dict[str, int]:
        """Conformance probe: removing again must find nothing anywhere."""
        return {name: count for name, count in (await self.remove(owner)).items() if count}
