"""Plugin catalogs (T038, T044; FR-026/027): a plugin registers its bundles (``{language: {namespace:
{key: message}}}``) under its own namespaces (``plugin.<key>`` prefix), owner-tagged; an invalid bundle is
rejected without affecting others; a plugin cannot change the portal default language; ``unregister``
removes everything an owner contributed (also on ``plugin.state_changed`` → disabled)."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from portalab.modules.i18n.render.icu import MessageSyntaxError, parse


class PluginCatalogError(ValueError):
    pass


@dataclass
class _Bundle:
    owner: str
    languages: tuple[str, ...]
    messages: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)


class PluginCatalogs:
    def __init__(self) -> None:
        self._bundles: dict[str, _Bundle] = {}

    def register(
        self,
        plugin_id: str,
        bundle: Mapping[str, Mapping[str, Mapping[str, str]]],
        *,
        owner: str | None = None,
    ) -> None:
        owner = owner or f"plugin:{plugin_id}"
        prefix = f"plugin.{plugin_id}"
        parsed = _Bundle(owner, tuple(sorted(bundle)))
        for language, namespaces in bundle.items():
            for namespace, messages in namespaces.items():
                if namespace != prefix and not namespace.startswith(f"{prefix}."):
                    raise PluginCatalogError(f"namespace {namespace!r} is outside {prefix!r}")
                for key, message in messages.items():
                    try:
                        parse(str(message))
                    except MessageSyntaxError as exc:
                        raise PluginCatalogError(f"{language}/{namespace}/{key}: {exc}") from exc
                parsed.messages[(namespace, language)] = {str(k): str(v) for k, v in messages.items()}
        self._bundles[plugin_id] = parsed

    def messages(self, namespace: str, language: str) -> dict[str, str]:
        merged: dict[str, str] = {}
        for bundle in self._bundles.values():
            merged.update(bundle.messages.get((namespace, language), {}))
        return merged

    def namespaces(self) -> set[str]:
        return {namespace for b in self._bundles.values() for namespace, _ in b.messages}

    def languages(self) -> dict[str, tuple[str, ...]]:
        return {plugin: b.languages for plugin, b in self._bundles.items()}

    def unregister(self, owner: str) -> int:
        doomed = [plugin for plugin, b in self._bundles.items() if b.owner == owner]
        for plugin in doomed:
            del self._bundles[plugin]
        return len(doomed)


default_plugin_catalogs = PluginCatalogs()


def register_plugin_catalog(plugin_id: str, bundle: Mapping[str, Mapping[str, Mapping[str, str]]]) -> None:
    default_plugin_catalogs.register(plugin_id, bundle)
