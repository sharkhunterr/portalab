"""Portalab plugin SDK (spec 023) — **the only import surface for plugins** (enforced by the install-time
import scanner). A plugin exposes ``register(ctx: PluginContext)``; everything it registers through the
context is recorded in the contribution ledger, owner-tagged ``plugin:<key>``, guarded (timeouts,
exceptions, quarantine) and removed when the plugin is disabled or quarantined. Core data is reachable
only through capabilities; the plugin's own tables live in schema ``plugin_<key>`` through ``ctx.db``.

Stability: ``portalab.sdk`` follows semver; breaking changes come with a major version and a deprecation
period (see ``docs/plugin-authoring.md``)."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from portalab.capabilities.ai import AITool, SourceRef, ToolResult
from portalab.capabilities.automation_actions import ActionType
from portalab.capabilities.community import DiscoveryShelf, ProfileSection, SectionResult
from portalab.capabilities.connector_sdk import Candidate, ServiceHandle, SourceRecord, TestResult
from portalab.capabilities.connector_sdk import Manifest as ConnectorManifest
from portalab.capabilities.content import CalendarItem, CalendarSourceResult
from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.events import ConsumerContext, Envelope
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.marketplace import ActivationResult, OwnershipView, ProductType
from portalab.capabilities.media_core import MediaType
from portalab.capabilities.search import ActionDef, FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.core.authz_port import Principal
from portalab.sdk.pages import Block, DataBlock, FormBlock, MarkdownBlock, PageDefinition

SDK_VERSION = "1.0.0"

RouteHandler = Callable[
    [Principal, Mapping[str, Any], Mapping[str, Any] | None], Awaitable[Mapping[str, Any]]
]
EventHandler = Callable[[Envelope, ConsumerContext], Awaitable[None]]


@runtime_checkable
class PluginDb(Protocol):
    """A session bound to the plugin's own PostgreSQL role and schema (``SET LOCAL ROLE``): core tables are
    unreachable; statements have a timeout."""

    async def execute(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> Sequence[Mapping[str, Any]]: ...


class PluginContext(Protocol):
    """Registration helpers handed to ``register(ctx)`` (see ``docs/plugin-authoring.md``)."""

    key: str
    db: PluginDb

    def nav_entry(
        self,
        key: str,
        label_key: str,
        route: str,
        *,
        permission: str,
        icon: str | None = None,
        group: str = "main",
        topic: str | None = None,
    ) -> None: ...

    def nav_section(
        self, key: str, label_key: str, *, icon: str | None = None, order_hint: int = 500
    ) -> None:
        """Declare a section ``plugin-<plugin key>[-<key>]`` for this plugin's entries (spec 027)."""
        ...

    def page(self, page: PageDefinition) -> None: ...

    def widget(self, definition: WidgetDefinition, provider: Any) -> None: ...

    def action(self, action: ActionDef) -> None: ...

    def search_provider(self, provider: Any) -> None: ...

    def calendar_source(self, source: Any) -> None: ...

    def statistics_pack(self, definitions: Sequence[Mapping[str, Any]]) -> None: ...

    def automation_action(self, action: ActionType) -> None: ...

    def ai_tool(self, tool: AITool) -> None: ...

    def notification_category(
        self, key: str, label_key: str, *, default_channels: Sequence[str] = ("portal",)
    ) -> None: ...

    def theme(self, document: Mapping[str, Any]) -> None: ...

    def i18n_catalog(self, bundle: Mapping[str, Mapping[str, Mapping[str, str]]]) -> None: ...

    def permission(self, name: str, description: str) -> str: ...

    def setting(self, name: str, schema: Any, default: Any, description: str) -> str: ...

    def event_type(self, name: str, *, schema: Any = None, automatable: bool = False) -> str: ...

    def consume(self, name: str, types: Sequence[str], handler: EventHandler) -> None: ...

    def provide(self, capability: str, provider: Any) -> None: ...

    def product_type(self, product_type: ProductType) -> None: ...

    def media_type(self, media_type: MediaType) -> None: ...

    def profile_section(self, section: ProfileSection) -> None: ...

    def discovery_shelf(self, shelf: DiscoveryShelf) -> None: ...

    def connector(self, connector: Any) -> None: ...

    def route(self, method: str, path: str, handler: RouteHandler, *, permission: str) -> None: ...


__all__ = [
    "SDK_VERSION",
    "AITool",
    "ActionDef",
    "ActionType",
    "ActivationResult",
    "BaseModel",
    "Block",
    "CalendarItem",
    "CalendarSourceResult",
    "Candidate",
    "ConnectorManifest",
    "ConsumerContext",
    "DataBlock",
    "DiscoveryShelf",
    "Envelope",
    "EventHandler",
    "FacetDef",
    "FormBlock",
    "LocaleContext",
    "MarkdownBlock",
    "MediaType",
    "OwnershipView",
    "PageDefinition",
    "ParsedQuery",
    "PluginContext",
    "PluginDb",
    "Principal",
    "ProductType",
    "ProfileSection",
    "ProviderResult",
    "Refresh",
    "RouteHandler",
    "SearchItem",
    "SectionResult",
    "ServiceHandle",
    "Size",
    "SizeLimits",
    "SourceRecord",
    "SourceRef",
    "TestResult",
    "ToolResult",
    "WidgetDefinition",
    "WidgetPayload",
]
