"""PluginContext (T016, T024; R7, R13, R14): the only way a plugin contributes. Each helper namespaces the
contribution (``plugin:<key>`` owner, ``plugin.<key>.*`` events, ``plugin:<key>.*`` permissions), wraps
any plugin callable in the PluginGuard, registers it with the owning registry and records it in the
contribution ledger. A registration that collides with another owner is recorded as a ``conflict`` (the
first owner keeps the slot) instead of breaking the load."""

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

from portalab.capabilities.ai import AITool
from portalab.capabilities.automation_actions import ActionType
from portalab.capabilities.community import DiscoveryShelf, ProfileSection
from portalab.capabilities.dashboard import WidgetDefinition, WidgetPayload
from portalab.capabilities.events import Consumer, EventType
from portalab.capabilities.marketplace import ProductType
from portalab.capabilities.media_core import MediaType
from portalab.capabilities.notifications import CategoryDef
from portalab.capabilities.plugins import I18N_CATALOGS, THEME_REGISTRY
from portalab.capabilities.registry import CapabilityError, CapabilitySpec
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.core.time import utc_now
from portalab.modules.plugins.context.registries import PluginRoute, Registries
from portalab.modules.plugins.guard.guard import GuardedCalendar, GuardedSearch, GuardedWidget, PluginGuard
from portalab.sdk import PluginDb
from portalab.sdk.pages import DataBlock, FormBlock, MarkdownBlock, PageDefinition

SYSTEM = Principal(channel="system")


class StaticWidget:
    """A declarative widget's data, straight from the manifest (no code)."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        self.data = dict(data)

    async def load(self, principal: Any, config: Any, ctx: Any) -> WidgetPayload:
        return WidgetPayload("available" if self.data else "no-data", as_of=utc_now(), data=self.data)


class Context:
    def __init__(
        self,
        key: str,
        registries: Registries,
        guard: PluginGuard,
        db: PluginDb,
        *,
        priority: int = 100,
    ) -> None:
        self.key = key
        self.owner = f"plugin:{key}"
        self.registries = registries
        self.guard = guard
        self.db = db
        self.priority = priority
        self.recorded: list[tuple[str, str, str, str | None]] = []  # (point, id, state, detail)
        self.themes: list[dict[str, Any]] = []  # registered asynchronously by ``flush``

    def _ok(self, point: str, contribution_id: str) -> None:
        self.recorded.append((point, contribution_id, "active", None))

    def _conflict(self, point: str, contribution_id: str, error: Exception) -> None:
        self.recorded.append(
            (point, contribution_id, "conflict", f"{type(error).__name__}: {str(error)[:200]}")
        )

    def _try(self, point: str, contribution_id: str, call: Any) -> None:
        try:
            call()
        except Exception as error:  # a collision or an invalid contribution never breaks the load
            self._conflict(point, contribution_id, error)
            return
        self._ok(point, contribution_id)

    # --- UI -----------------------------------------------------------------------------------------------
    def nav_entry(
        self,
        key: str,
        label_key: str,
        route: str,
        *,
        permission: str,
        icon: str | None = None,
        group: str = "main",
    ) -> None:
        entry_key = f"plugin_{self.key}.{key}"
        contribution: dict[str, Any] = {
            "key": entry_key,
            "owner": self.owner,
            "kind": "entry",
            "label_key": label_key,
            "route": route,
            "icon": icon,
            "group": group,
            "order_hint": 500,
            "required_permission": permission,
        }
        self._try(
            "nav",
            contribution["key"],
            lambda: self.registries.navigation.register(contribution, owner=self.owner),
        )

    def page(self, page: PageDefinition) -> None:
        self._try("page", page.key, lambda: self.registries.pages.register(self.key, page))
        if page.nav_label_key:
            self.nav_entry(
                f"page_{page.key}",
                page.nav_label_key,
                f"/plugins/{self.key}/{page.key}",
                permission=page.required_permission,
            )

    def widget(self, definition: WidgetDefinition, provider: Any) -> None:
        guarded = GuardedWidget(self.guard, self.key, provider)
        self._try(
            "widget",
            definition.key,
            lambda: self.registries.widgets.register(definition, guarded, owner=self.owner),
        )

    def action(self, action: Any) -> None:
        """A palette action (004/008 ``ActionDef``)."""
        self._try(
            "action", action.id, lambda: self.registries.search.register_action(action, owner=self.owner)
        )

    def search_provider(self, provider: Any) -> None:
        guarded = GuardedSearch(self.guard, self.key, provider)
        self._try("search", provider.kind, lambda: self.registries.search.register(guarded, owner=self.owner))

    def calendar_source(self, source: Any) -> None:
        guarded = GuardedCalendar(self.guard, self.key, source)
        self._try(
            "calendar", source.kind, lambda: self.registries.calendar.register(guarded, owner=self.owner)
        )

    def statistics_pack(self, definitions: Sequence[Mapping[str, Any]]) -> None:
        domain = f"plugin_{self.key}"
        self._try(
            "statistics",
            domain,
            lambda: self.registries.packs.register(domain, list(definitions), owner=self.owner),
        )

    # --- automation, AI, notifications ------------------------------------------------------------------
    def automation_action(self, action: ActionType) -> None:
        guarded = dataclasses.replace(
            action, run=self.guard.wrap(self.key, "action", action.run), owner=self.owner
        )
        self._try("automation_action", action.key, lambda: self.registries.actions.register(guarded))

    def ai_tool(self, tool: AITool) -> None:
        guarded = dataclasses.replace(
            tool, handler=self.guard.wrap(self.key, "hook", tool.handler), owner=self.owner
        )
        self._try("ai_tool", tool.name, lambda: self.registries.ai_tools.register(guarded))

    def notification_category(
        self, key: str, label_key: str, *, default_channels: Sequence[str] = ("portal",)
    ) -> None:
        full = f"{self.owner}.{key}"
        self._try(
            "notification_category",
            full,
            lambda: self.registries.categories.declare(
                CategoryDef(full, self.owner, label_key, default_channels=tuple(default_channels))
            ),
        )

    # --- themes and messages (module-owned registries, through ports) ----------------------------------
    def theme(self, document: Mapping[str, Any]) -> None:
        self.themes.append(dict(document))

    async def flush(self) -> None:
        """Register what needs an async port (themes, 022) after ``register(ctx)`` returned."""
        providers = self.registries.capabilities.system_providers(THEME_REGISTRY)
        for document in self.themes:
            key = str(document.get("key", "?"))
            if not providers:
                self._conflict("theme", key, RuntimeError("themes unavailable"))
                continue
            try:
                try:  # a plugin enabled again gets its (withdrawn) theme back
                    await providers[0].provider.update(SYSTEM, key, definition=document, enabled=True)
                except NotFound:
                    await providers[0].provider.register(
                        SYSTEM, document, source=f"plugin:{self.key}", owner=self.owner
                    )
            except Exception as error:
                self._conflict("theme", key, error)
                continue
            self._ok("theme", key)
        self.themes = []

    def i18n_catalog(self, bundle: Mapping[str, Mapping[str, Mapping[str, str]]]) -> None:
        providers = self.registries.capabilities.system_providers(I18N_CATALOGS)
        if not providers:
            self._conflict("i18n", self.key, RuntimeError("catalogs unavailable"))
            return
        self._try(
            "i18n",
            f"plugin.{self.key}",
            lambda: providers[0].provider.register(self.key, bundle, owner=self.owner),
        )

    # --- declarations -------------------------------------------------------------------------------------
    def permission(self, name: str, description: str, *, user_grantable: bool = False) -> str:
        full = f"plugin:{self.key}.{name}"
        self._try(
            "permission",
            full,
            lambda: self.registries.permissions.declare(
                full, description, owner=self.owner, user_grantable=user_grantable
            ),
        )
        return full

    def setting(self, name: str, schema: Any, default: Any, description: str) -> str:
        full = f"plugin.{self.key}.{name}"
        self._try(
            "setting",
            full,
            lambda: self.registries.settings.declare(
                scope="plugin",
                key=full,
                schema=schema,
                default=default,
                owner=self.owner,
                description=description,
            ),
        )
        return full

    def event_type(self, name: str, *, schema: Any = None, automatable: bool = False) -> str:
        full = f"plugin.{self.key}.{name}"
        self._try(
            "automation_trigger" if automatable else "event_type",
            full,
            lambda: self.registries.event_types.register(
                EventType(
                    name=full,
                    owner=self.owner,
                    schema=schema,
                    open_payload=schema is None,
                    automatable=automatable,
                )
            ),
        )
        return full

    def consume(self, name: str, types: Sequence[str], handler: Any) -> None:
        full = f"plugin.{self.key}.{name}"
        guarded = self.guard.wrap(self.key, "event", handler)
        self._try(
            "event_consumer",
            full,
            lambda: self.registries.consumers.register(Consumer(full, frozenset(types), guarded, self.owner)),
        )

    def provide(self, capability: str, provider: Any) -> None:
        if capability.startswith(f"plugin.{self.key}."):  # a capability the plugin exposes to other plugins
            try:
                self.registries.capabilities.spec(capability)
            except CapabilityError:
                self.registries.capabilities.declare(
                    CapabilitySpec(
                        name=capability,
                        version="1.0",
                        protocol=object,
                        multi_provider=False,
                        description=f"Provided by plugin {self.key}",
                    )
                )
        self._try(
            "capability",
            capability,
            lambda: self.registries.capabilities.provide(
                capability, provider, instance_ref=self.owner, owner=self.owner, priority=self.priority
            ),
        )

    # --- domain registries -------------------------------------------------------------------------------
    def product_type(self, product_type: ProductType) -> None:
        self._try(
            "product_type", product_type.key, lambda: self.registries.product_types.register(product_type)
        )

    def media_type(self, media_type: MediaType) -> None:
        self._try("media_type", media_type.kind, lambda: self.registries.media_types.register(media_type))

    def profile_section(self, section: ProfileSection) -> None:
        guarded = dataclasses.replace(section, provider=self.guard.wrap(self.key, "widget", section.provider))
        self._try("profile_section", section.key, lambda: self.registries.sections.register(guarded))

    def discovery_shelf(self, shelf: DiscoveryShelf) -> None:
        guarded = dataclasses.replace(shelf, provider=self.guard.wrap(self.key, "widget", shelf.provider))
        self._try("discovery_shelf", shelf.key, lambda: self.registries.shelves.register(guarded))

    def connector(self, connector: Any) -> None:
        self._try(
            "connector",
            connector.key,
            lambda: self.registries.connectors.register(connector, owner=self.owner),
        )

    def route(self, method: str, path: str, handler: Any, *, permission: str) -> None:
        clean = path.strip("/")
        self._try(
            "route",
            f"{method.upper()} {clean}",
            lambda: self.registries.routes.register(
                PluginRoute(
                    self.key, method.upper(), clean, permission, self.guard.wrap(self.key, "route", handler)
                )
            ),
        )


def page_from(raw: Mapping[str, Any]) -> PageDefinition:
    blocks: list[Any] = []
    for block in raw.get("blocks", []):
        kind = block.get("kind")
        if kind == "markdown":
            blocks.append(MarkdownBlock(str(block.get("text", ""))[:20_000]))
        elif kind in ("stat", "list", "table", "chart"):
            blocks.append(
                DataBlock(
                    kind,
                    str(block.get("title_key", "")),
                    str(block.get("data", "")),
                    tuple(block.get("columns", ())),
                    block.get("chart", "line"),
                )
            )
        elif kind == "form":
            blocks.append(
                FormBlock(
                    str(block.get("title_key", "")),
                    dict(block.get("schema", {})),
                    str(block.get("action", "")),
                )
            )
    return PageDefinition(
        key=str(raw["key"]),
        title_key=str(raw.get("title_key", raw["key"])),
        required_permission=str(raw["permission"]),
        blocks=tuple(blocks),
        nav_label_key=raw.get("nav_label_key"),
    )


def apply_manifest(ctx: Context, manifest: Mapping[str, Any]) -> None:
    """Declarative (Tier 1) contributions — no plugin code runs."""
    for permission in manifest.get("permissions", []):
        ctx.permission(permission["name"], permission["description"])
    if manifest.get("scope") == "user":
        ctx.permission(
            "use",
            "Use this plugin (granted per member, e.g. by a Marketplace acquisition)",
            user_grantable=True,
        )
    types = {"string": str, "integer": int, "boolean": bool, "number": float}
    for setting in manifest.get("settings", []):
        ctx.setting(
            setting["name"], types[setting["type"]], setting["default"], setting.get("description", "")
        )
    for name in manifest.get("events", {}).get("produces", []):
        ctx.event_type(name)
    ui = manifest.get("ui", {})
    for entry in ui.get("nav", []):
        ctx.nav_entry(
            str(entry["key"]),
            str(entry["label_key"]),
            str(entry["route"]),
            permission=str(entry["permission"]),
            icon=entry.get("icon"),
            group=str(entry.get("group", "main")),
        )
    for raw in ui.get("pages", []):
        ctx.page(page_from(raw))
    for widget in ui.get("widgets", []):
        definition = WidgetDefinition(
            key=f"plugin:{ctx.key}.{widget['key']}",
            owner=ctx.owner,
            title_key=str(widget["title_key"]),
            required_permission=str(widget["permission"]),
            template=str(widget.get("template", "stat")),
        )
        ctx.widget(definition, StaticWidget(widget.get("data", {})))
    for category in ui.get("notification_categories", []):
        ctx.notification_category(str(category["name"]), str(category["label_key"]))
    if ui.get("statistics"):
        ctx.statistics_pack(ui["statistics"])
    for theme in ui.get("themes", []):
        ctx.theme(theme)
    if manifest.get("i18n"):
        ctx.i18n_catalog(manifest["i18n"])
