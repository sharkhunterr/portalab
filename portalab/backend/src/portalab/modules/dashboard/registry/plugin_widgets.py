"""Declarative Marketplace/plugin widgets (T031; R11): a plugin contributes a widget as **data + one of the
standard templates** (``stat|list|chart|timeline|status``) — never its own code in the SPA. Keys are
namespaced ``plugin:<key>.<widget>``; string settings are hardened (no markup, bounded length); the
widget obeys the same permissions, policies and states as first-party ones. Disabling the plugin removes
its widgets (``plugin.state_changed``); users' instances stay as placeholders and come back on
reactivation with their settings."""

import copy
from collections.abc import Mapping
from typing import Any

from portalab.capabilities.dashboard import (
    Refresh,
    Size,
    SizeLimits,
    WidgetDataProvider,
    WidgetDefinition,
    WidgetRegistry,
)
from portalab.capabilities.events import Consumer, ConsumerContext, Envelope

CONSUMER = "dashboard.plugin_widgets"
SAFE_TEXT = r"^[^<>]*$"


def harden(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Every string in a plugin config schema refuses markup and is length-bounded."""
    out = copy.deepcopy(dict(schema))

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "string":
                node.setdefault("maxLength", 200)
                node["pattern"] = SAFE_TEXT
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(out)
    out.setdefault("additionalProperties", False)
    return out


def plugin_definition(plugin_id: str, manifest: Mapping[str, Any]) -> WidgetDefinition:
    name = str(manifest["name"])
    size = manifest.get("size") or {}
    return WidgetDefinition(
        key=f"plugin:{plugin_id}.{name}",
        owner=f"plugin:{plugin_id}",
        title_key=str(manifest.get("title_key", f"plugin.{plugin_id}:{name}")),
        description_key=manifest.get("description_key"),
        required_permission=str(manifest.get("permission", f"plugin:{plugin_id}.use")),
        config_schema=harden(manifest.get("config_schema") or {"type": "object", "properties": {}}),
        config_defaults=dict(manifest.get("config_defaults") or {}),
        size=SizeLimits(default=Size(int(size.get("w", 4)), int(size.get("h", 2)))),
        refresh=Refresh(events=tuple(manifest.get("invalidate_on") or ())),
        stale_after_s=manifest.get("stale_after_s"),
        template=str(manifest.get("template", "")),
        product=manifest.get("product"),
    )


def register_plugin_widget(
    registry: WidgetRegistry, plugin_id: str, manifest: Mapping[str, Any], provider: WidgetDataProvider
) -> WidgetDefinition:
    definition = plugin_definition(plugin_id, manifest)
    registry.register(definition, provider, owner=f"plugin:{plugin_id}")
    return definition


def plugin_state_consumer(registry: WidgetRegistry) -> Consumer:
    async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
        plugin_id = str(envelope.payload.get("plugin_id", ""))
        if plugin_id and envelope.payload.get("state") in (
            "disabled",
            "uninstalled",
            "error",
            "incompatible",
        ):
            registry.unregister_owner(f"plugin:{plugin_id}")

    return Consumer(
        CONSUMER, frozenset({"plugin.state_changed"}), handle, "module:dashboard", replay_safe=True
    )
