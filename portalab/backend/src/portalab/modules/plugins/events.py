"""Plugin event types (T003): ``plugin.installed|enabled|disabled|updated|update_failed|rolled_back|
quarantined|archived|purged|configuration_changed`` and the umbrella ``plugin.state_changed`` consumed by
the registries of other modules (payload ``plugin_id``/``plugin``, ``from_state``, ``state``,
``reason``; dedup ``(plugin_key, seq)``)."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:plugins"
LIFECYCLE = (
    "plugin.installed",
    "plugin.enabled",
    "plugin.disabled",
    "plugin.updated",
    "plugin.update_failed",
    "plugin.rolled_back",
    "plugin.quarantined",
    "plugin.archived",
    "plugin.purged",
    "plugin.configuration_changed",
    "plugin.incompatible",
)


class PluginChanged(BaseModel):
    plugin: str
    version: str | None = None


class PluginStateChanged(BaseModel):
    plugin_id: str
    plugin: str
    from_state: str | None
    state: str
    reason: str | None = None
    seq: int


def register_event_types(registry: EventTypeRegistry) -> None:
    for name in LIFECYCLE:
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=PluginChanged,
                    open_payload=False,
                    visibility_class="restricted",
                )
            )
    if registry.get("plugin.state_changed") is None:
        registry.register(
            EventType(
                name="plugin.state_changed",
                owner=OWNER,
                schema=PluginStateChanged,
                open_payload=False,
                visibility_class="restricted",
            )
        )
